local stub = {}

local sep = package.config:sub(1, 1)

local function join_path(...)
    local parts = {}
    for i = 1, select("#", ...) do
        local value = select(i, ...)
        if value and value ~= "" then
            local text = tostring(value):gsub("[/\\]+", sep)
            if text ~= "" then
                parts[#parts + 1] = text
            end
        end
    end
    local joined = table.concat(parts, sep)
    joined = joined:gsub(sep .. "+", sep)
    return joined
end

local function dirname(path)
    local normalized = tostring(path):gsub("[/\\]+", sep)
    local stripped = normalized:gsub(sep .. "+$", "")
    local idx = stripped:match("^.*()" .. "%" .. sep)
    if not idx then
        return ""
    end
    return stripped:sub(1, idx - 1)
end

local function is_absolute(path)
    path = tostring(path)
    if sep == "\\" then
        return path:match("^%a:[/\\]") ~= nil or path:sub(1, 2) == "\\\\"
    end
    return path:sub(1, 1) == "/"
end

local function shell_quote(path)
    return "'" .. tostring(path):gsub("'", "'\\''") .. "'"
end

local function stat_path(path)
    local file = io.open(path, "rb")
    if file then
        local size = file:seek("end") or 0
        file:close()
        return {type = "file", size = size}
    end

    local ok = os.rename(path, path)
    if ok then
        return {type = "directory", size = 0}
    end

    return nil
end

local function path_exists(path)
    return stat_path(path) ~= nil
end

local function mkdir_p(path)
    if not path or path == "" or path_exists(path) then
        return true
    end

    if sep == "\\" then
        os.execute('mkdir "' .. tostring(path) .. '" >NUL 2>NUL')
        return path_exists(path)
    end

    os.execute("mkdir -p " .. shell_quote(path) .. " >/dev/null 2>&1")
    return path_exists(path)
end

local function list_directory(path)
    local items = {}
    local handle

    if sep == "\\" then
        handle = io.popen('dir /b "' .. tostring(path) .. '" 2>NUL')
    else
        handle = io.popen("ls -1A " .. shell_quote(path) .. " 2>/dev/null")
    end

    if not handle then
        return items
    end

    for line in handle:lines() do
        if line ~= "." and line ~= ".." and line ~= "" then
            items[#items + 1] = line
        end
    end
    handle:close()
    table.sort(items)
    return items
end

local function read_binary_file(path)
    local file = io.open(path, "rb")
    if not file then
        return nil
    end
    local contents = file:read("*a")
    file:close()
    return contents
end

local function write_binary_file(path, contents, mode)
    local parent = dirname(path)
    if parent ~= "" then
        mkdir_p(parent)
    end

    local file = assert(io.open(path, mode or "wb"))
    file:write(contents)
    file:close()
    return true
end

local function decode_png_size(path)
    local data = read_binary_file(path)
    if not data or #data < 24 then
        return 1, 1
    end

    if data:sub(1, 8) ~= "\137PNG\r\n\026\n" then
        return 1, 1
    end

    local bytes = {data:byte(17, 24)}
    if #bytes < 8 then
        return 1, 1
    end

    local function u32(a, b, c, d)
        return (((a * 256) + b) * 256 + c) * 256 + d
    end

    return u32(bytes[1], bytes[2], bytes[3], bytes[4]), u32(bytes[5], bytes[6], bytes[7], bytes[8])
end

local function strip_source_prefix(path)
    if type(path) ~= "string" then
        return path
    end
    return path:gsub("^@", "")
end

local function module_dir()
    local source = strip_source_prefix(debug.getinfo(1, "S").source)
    return dirname(source)
end

local function infer_source_root()
    return join_path(module_dir(), "..", "Balatro")
end

local function infer_mod_root()
    return join_path(module_dir(), "..")
end

local function ensure_trailing_sep(path)
    local normalized = tostring(path or ""):gsub("[/\\]+", sep)
    if normalized:sub(-1) ~= sep then
        normalized = normalized .. sep
    end
    return normalized
end

local state = {
    installed = false,
    source_root = nil,
    save_root = nil,
    mod_root = nil,
    os_name = os.getenv("BALATRO_HEADLESS_OS") or "Linux",
    width = 1280,
    height = 720,
    window_title = "Balatro Headless",
    mouse_x = 0,
    mouse_y = 0,
    mouse_visible = true,
    clipboard = "",
    graphics_active = true,
    graphics_created = true,
    window_open = true,
    current_shader = nil,
    current_canvas = nil,
    current_font = nil,
    touches = {},
    joysticks = {},
    channels = {},
    audio_sources = {},
    event_queue = {},
    quit_requested = false,
    fixed_dt = 1 / 60,
    time_offset = 0,
    start_clock = os.clock(),
    display_modes = {
        {width = 1280, height = 720},
        {width = 1920, height = 1080},
    },
}

stub.state = state

local function now()
    return (os.clock() - state.start_clock) + state.time_offset
end

local function resolve_save_path(path)
    if is_absolute(path) then
        return path
    end
    return join_path(state.save_root, path)
end

local function resolve_read_path(path)
    if is_absolute(path) then
        return path
    end

    local save_path = join_path(state.save_root, path)
    if path_exists(save_path) then
        return save_path
    end

    local source_path = join_path(state.source_root, path)
    if path_exists(source_path) then
        return source_path
    end

    return source_path
end

local function install_package_path()
    local search_roots = {
        join_path(state.source_root, "?.lua"),
        join_path(state.source_root, "?", "init.lua"),
    }

    for _, pattern in ipairs(search_roots) do
        if not package.path:find(pattern, 1, true) then
            package.path = pattern .. ";" .. package.path
        end
    end
end

local function install_bit_compat()
    if package.loaded.bit then
        return
    end

    package.preload.bit = function()
        if bit32 then
            return {
                bxor = bit32.bxor,
                lshift = bit32.lshift,
                rshift = bit32.rshift,
            }
        end

        local function u32(value)
            value = value % 4294967296
            if value < 0 then
                value = value + 4294967296
            end
            return value
        end

        local function bxor(a, b)
            a = u32(a or 0)
            b = u32(b or 0)

            local result = 0
            local place = 1

            while a > 0 or b > 0 do
                local abit = a % 2
                local bbit = b % 2
                if abit ~= bbit then
                    result = result + place
                end
                a = math.floor(a / 2)
                b = math.floor(b / 2)
                place = place * 2
            end

            return u32(result)
        end

        local function lshift(a, b)
            return u32((a or 0) * (2 ^ (b or 0)))
        end

        local function rshift(a, b)
            return math.floor(u32(a or 0) / (2 ^ (b or 0)))
        end

        return {
            bxor = bxor,
            lshift = lshift,
            rshift = rshift,
        }
    end
end

local function install_utf8_compat()
    utf8 = utf8 or {}
    if not utf8.chars then
        function utf8.chars(text)
            local index = 1
            local length = #text
            return function()
                if index > length then
                    return nil
                end

                local start_index = index
                local first = text:byte(index)

                if first < 0x80 then
                    index = index + 1
                elseif first < 0xE0 then
                    index = index + 2
                elseif first < 0xF0 then
                    index = index + 3
                else
                    index = index + 4
                end

                return text:sub(start_index, index - 1)
            end
        end
    end
end

local function install_loadstring_compat()
    if not _G.loadstring then
        _G.loadstring = _G.load
    end
end

local function make_channel(name)
    return {
        name = name,
        queue = {},
        push = function(self, value)
            self.queue[#self.queue + 1] = value
            return true
        end,
        pop = function(self)
            if #self.queue == 0 then
                return nil
            end
            return table.remove(self.queue, 1)
        end,
        demand = function(self)
            return self:pop()
        end,
    }
end

local function make_source(path, kind)
    local source = {
        path = path,
        kind = kind or "static",
        playing = false,
        volume = 1,
        pitch = 1,
    }

    function source:play()
        self.playing = true
        return true
    end

    function source:pause()
        self.playing = false
    end

    function source:stop()
        self.playing = false
    end

    function source:isPlaying()
        return self.playing
    end

    function source:setVolume(volume)
        self.volume = volume
    end

    function source:setPitch(pitch)
        self.pitch = pitch
    end

    function source:release()
        self.playing = false
    end

    state.audio_sources[#state.audio_sources + 1] = source
    return source
end

local function make_font(path, size)
    local font = {
        path = path,
        size = size or 12,
    }

    function font:getWidth(text)
        return math.floor(#tostring(text or "") * self.size * 0.6 + 0.5)
    end

    function font:getHeight()
        return self.size
    end

    function font:setFilter()
    end

    return font
end

local function make_text(font, initial)
    local text = {
        font = font,
        contents = "",
    }

    function text:set(value)
        if type(value) == "table" then
            self.contents = tostring(value[2] or value[1] or "")
        else
            self.contents = tostring(value or "")
        end
    end

    text:set(initial)
    return text
end

local function make_image(path)
    local width, height = decode_png_size(resolve_read_path(path))
    local image = {
        path = path,
        width = width,
        height = height,
    }

    function image:getDimensions()
        return self.width, self.height
    end

    function image:getWidth()
        return self.width
    end

    function image:getHeight()
        return self.height
    end

    function image:setFilter()
    end

    return image
end

local function make_quad(x, y, w, h, sw, sh)
    local quad = {
        x = x,
        y = y,
        w = w,
        h = h,
        sw = sw,
        sh = sh,
    }

    function quad:setViewport(nx, ny, nw, nh)
        self.x = nx
        self.y = ny
        self.w = nw
        self.h = nh
    end

    return quad
end

local function make_shader(source)
    local shader = {
        source = source,
        uniforms = {},
    }

    function shader:send(name, value)
        self.uniforms[name] = value
    end

    return shader
end

local function make_canvas(width, height)
    local canvas = {
        width = width,
        height = height,
    }

    function canvas:getWidth()
        return self.width
    end

    function canvas:getHeight()
        return self.height
    end

    function canvas:getPixelWidth()
        return self.width
    end

    function canvas:getPixelHeight()
        return self.height
    end

    function canvas:getDimensions()
        return self.width, self.height
    end

    function canvas:release()
    end

    function canvas:setFilter()
    end

    return canvas
end

local function make_video(path)
    local source = make_source(path, "stream")
    local video = {
        path = path,
        width = 320,
        height = 240,
        source = source,
        playing = false,
        position = 0,
    }

    function video:getWidth()
        return self.width
    end

    function video:getHeight()
        return self.height
    end

    function video:getSource()
        return self.source
    end

    function video:play()
        self.playing = true
        self.source:play()
    end

    function video:pause()
        self.playing = false
        self.source:pause()
    end

    function video:seek(position)
        self.position = position or 0
    end

    function video:release()
        self.playing = false
        self.source:release()
    end

    return video
end

local function make_thread(source)
    return {
        source = source,
        started = false,
        args = nil,
        start = function(self, ...)
            self.started = true
            self.args = {...}
            return true
        end,
    }
end

local function make_joystick(name)
    local joystick = {
        name = name or "Headless Gamepad",
    }

    function joystick:isGamepad()
        return true
    end

    function joystick:getGamepadMappingString()
        return "0000000000000000," .. self.name .. ",platform:Headless"
    end

    function joystick:getGamepadAxis()
        return 0
    end

    return joystick
end

stub.make_joystick = make_joystick

function stub.push_event(name, ...)
    state.event_queue[#state.event_queue + 1] = {name, ...}
end

function stub.advance(seconds)
    state.time_offset = state.time_offset + (seconds or state.fixed_dt)
end

function stub.set_mouse_position(x, y)
    state.mouse_x = x or state.mouse_x
    state.mouse_y = y or state.mouse_y
end

function stub.setup(options)
    options = options or {}

    if options.source_root then
        state.source_root = options.source_root
    end
    if options.save_root then
        state.save_root = options.save_root
    end
    if options.mod_root then
        state.mod_root = options.mod_root
    end
    if options.os_name then
        state.os_name = options.os_name
    end
    if options.width then
        state.width = options.width
    end
    if options.height then
        state.height = options.height
    end
    if options.fixed_dt then
        state.fixed_dt = options.fixed_dt
    end

    state.source_root = state.source_root or infer_source_root()
    state.save_root = state.save_root or os.getenv("BALATRO_SAVE_DIR") or join_path(module_dir(), ".save")
    state.mod_root = state.mod_root or infer_mod_root()
    mkdir_p(state.save_root)
    install_package_path()
    install_bit_compat()
    install_utf8_compat()
    install_loadstring_compat()

    love = love or {}
    love._headless_stub = true
    love._stub_state = state

    love.arg = love.arg or {}
    function love.arg.parseGameArguments(args)
        return args or {}
    end

    love.audio = love.audio or {}
    function love.audio.newSource(path, kind)
        return make_source(path, kind)
    end
    function love.audio.play(source)
        if source and source.play then
            return source:play()
        end
        return true
    end
    function love.audio.stop()
        for _, source in ipairs(state.audio_sources) do
            source:stop()
        end
    end

    love.data = love.data or {}
    function love.data.compress(_, _, value)
        return value
    end
    function love.data.decompress(_, _, value)
        return value
    end

    love.event = love.event or {}
    function love.event.pump()
    end
    function love.event.poll()
        local index = 0
        return function()
            index = index + 1
            local event = state.event_queue[index]
            if not event then
                state.event_queue = {}
                return nil
            end
            return table.unpack(event)
        end
    end
    function love.event.quit(code)
        state.quit_requested = true
        stub.push_event("quit", code or 0)
        return true
    end

    love.filesystem = love.filesystem or {}
    function love.filesystem.getSourceBaseDirectory()
        return state.source_root
    end
    function love.filesystem.getInfo(path)
        local resolved = resolve_read_path(path)
        return stat_path(resolved)
    end
    function love.filesystem.getDirectoryItems(path)
        return list_directory(resolve_read_path(path))
    end
    function love.filesystem.read(path)
        return read_binary_file(resolve_read_path(path))
    end
    function love.filesystem.write(path, contents)
        return write_binary_file(resolve_save_path(path), contents or "", "wb")
    end
    function love.filesystem.append(path, contents)
        return write_binary_file(resolve_save_path(path), contents or "", "ab")
    end
    function love.filesystem.createDirectory(path)
        return mkdir_p(resolve_save_path(path))
    end
    function love.filesystem.remove(path)
        local target = resolve_save_path(path)
        if sep == "\\" then
            os.remove(target)
            return true
        end
        os.execute("rm -rf " .. shell_quote(target) .. " >/dev/null 2>&1")
        return true
    end

    love.graphics = love.graphics or {}
    function love.graphics.clear()
    end
    function love.graphics.draw()
    end
    function love.graphics.getHeight()
        return state.height
    end
    function love.graphics.getWidth()
        return state.width
    end
    function love.graphics.isActive()
        return state.graphics_active
    end
    function love.graphics.isCreated()
        return state.graphics_created
    end
    function love.graphics.newCanvas(width, height)
        return make_canvas(width, height)
    end
    function love.graphics.newFont(path, size)
        return make_font(path, size)
    end
    function love.graphics.newImage(path)
        return make_image(path)
    end
    function love.graphics.newQuad(x, y, w, h, sw, sh)
        return make_quad(x, y, w, h, sw, sh)
    end
    function love.graphics.newShader(source)
        return make_shader(source)
    end
    function love.graphics.newText(font, initial)
        return make_text(font, initial)
    end
    function love.graphics.newVideo(path)
        return make_video(path)
    end
    function love.graphics.origin()
    end
    function love.graphics.polygon()
    end
    function love.graphics.pop()
    end
    function love.graphics.present()
    end
    function love.graphics.print()
    end
    function love.graphics.printf()
    end
    function love.graphics.push()
    end
    function love.graphics.rectangle()
    end
    function love.graphics.reset()
        state.current_shader = nil
        state.current_canvas = nil
    end
    function love.graphics.rotate()
    end
    function love.graphics.scale()
    end
    function love.graphics.setCanvas(target)
        if type(target) == "table" and not target.width and target[1] then
            state.current_canvas = target[1]
        else
            state.current_canvas = target
        end
    end
    function love.graphics.setColor()
    end
    function love.graphics.setDefaultFilter()
    end
    function love.graphics.setLineStyle()
    end
    function love.graphics.setLineWidth()
    end
    function love.graphics.setNewFont(path, size)
        state.current_font = make_font(path, size)
        return state.current_font
    end
    function love.graphics.setShader(shader)
        state.current_shader = shader
    end
    function love.graphics.translate()
    end

    love.joystick = love.joystick or {}
    function love.joystick.getJoysticks()
        return state.joysticks
    end
    function love.joystick.loadGamepadMappings()
        return true
    end

    love.mouse = love.mouse or {}
    function love.mouse.getPosition()
        return state.mouse_x, state.mouse_y
    end
    function love.mouse.isVisible()
        return state.mouse_visible
    end
    function love.mouse.setGrabbed()
    end
    function love.mouse.setRelativeMode()
    end
    function love.mouse.setVisible(visible)
        state.mouse_visible = not not visible
    end

    love.sound = love.sound or {}

    love.system = love.system or {}
    function love.system.getClipboardText()
        return state.clipboard
    end
    function love.system.getOS()
        return state.os_name
    end
    function love.system.openURL()
        return true
    end
    function love.system.setClipboardText(text)
        state.clipboard = tostring(text or "")
    end

    love.thread = love.thread or {}
    function love.thread.getChannel(name)
        state.channels[name] = state.channels[name] or make_channel(name)
        return state.channels[name]
    end
    function love.thread.newThread(source)
        return make_thread(source)
    end

    love.timer = love.timer or {}
    function love.timer.getFPS()
        return math.floor(1 / state.fixed_dt + 0.5)
    end
    function love.timer.getTime()
        return now()
    end
    function love.timer.sleep(seconds)
        stub.advance(seconds or 0)
    end
    function love.timer.step()
        stub.advance(state.fixed_dt)
        return state.fixed_dt
    end

    love.touch = love.touch or {}
    function love.touch.getTouches()
        return state.touches
    end

    love.window = love.window or {}
    function love.window.getDesktopDimensions()
        return state.width, state.height
    end
    function love.window.getDisplayCount()
        return 1
    end
    function love.window.getFullscreenModes()
        return state.display_modes
    end
    function love.window.getMode()
        return state.width, state.height
    end
    function love.window.getTitle()
        return state.window_title
    end
    function love.window.isOpen()
        return state.window_open
    end
    function love.window.setMode(width, height)
        state.width = width or state.width
        state.height = height or state.height
        state.window_open = true
        state.graphics_created = true
        return true
    end
    function love.window.showMessageBox(_, _, buttons)
        return buttons and #buttons or 1
    end
    function love.window.toPixels(value)
        return value
    end
    function love.window.updateMode(width, height)
        return love.window.setMode(width, height)
    end

    love.quit = love.event.quit

    love.handlers = love.handlers or {}
    setmetatable(love.handlers, {
        __index = function(_, name)
            return function(...)
                local handler = love[name]
                if type(handler) == "function" then
                    return handler(...)
                end
            end
        end,
    })

    package.preload.love = function()
        return love
    end

    local love_modules = {
        "arg",
        "audio",
        "data",
        "event",
        "filesystem",
        "graphics",
        "joystick",
        "mouse",
        "sound",
        "system",
        "thread",
        "timer",
        "touch",
        "window",
    }

    for _, module_name in ipairs(love_modules) do
        package.preload["love." .. module_name] = function()
            return love[module_name]
        end
    end

    local function install_logger(level)
        return function(message, _)
            io.stderr:write("[" .. level .. "] " .. tostring(message), "\n")
        end
    end

    sendDebugMessage = install_logger("DEBUG")
    sendInfoMessage = install_logger("INFO")
    sendWarnMessage = install_logger("WARN")
    sendErrorMessage = install_logger("ERROR")

    SMODS = {
        load_file = function(path)
            local resolved = join_path(state.mod_root, path)
            return loadfile(resolved)
        end,
        current_mod = {
            path = ensure_trailing_sep(state.mod_root),
            version = "headless",
        },
    }

    state.installed = true
    stub.love = love
    return love
end

return stub
