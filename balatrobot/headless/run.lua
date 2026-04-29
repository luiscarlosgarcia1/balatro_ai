local stub = require("headless.love_stub")

local FIXED_DT = 1 / 60
local SEP = package.config:sub(1, 1)

local function join_path(...)
    local parts = {}
    for i = 1, select("#", ...) do
        local value = select(i, ...)
        if value and value ~= "" then
            local text = tostring(value):gsub("[/\\]+", SEP)
            if text ~= "" then
                parts[#parts + 1] = text
            end
        end
    end

    local joined = table.concat(parts, SEP)
    return joined:gsub(SEP .. "+", SEP)
end

local function dirname(path)
    local normalized = tostring(path):gsub("[/\\]+", SEP)
    local stripped = normalized:gsub(SEP .. "+$", "")
    local idx = stripped:match("^.*()" .. "%" .. SEP)
    if not idx then
        return ""
    end
    return stripped:sub(1, idx - 1)
end

local function strip_source_prefix(path)
    if type(path) ~= "string" then
        return path
    end
    return path:gsub("^@", "")
end

local function infer_source_root()
    local source = strip_source_prefix(debug.getinfo(1, "S").source)
    local run_dir = dirname(source)
    return join_path(run_dir, "..", "Balatro")
end

stub.setup({
    source_root = infer_source_root(),
    fixed_dt = FIXED_DT,
})

local function shutdown(exit_code)
    if type(BB_SERVER) == "table" and type(BB_SERVER.close) == "function" then
        pcall(BB_SERVER.close)
    end

    if not stub.state.quit_requested then
        if type(love) == "table" and type(love.quit) == "function" then
            pcall(love.quit)
        end
    end

    os.exit(exit_code or 0)
end

local function boot_game()
    local main_path = join_path(stub.state.source_root, "main.lua")
    local chunk, err = loadfile(main_path)
    if not chunk then
        error("Could not load main.lua: " .. tostring(err))
    end

    chunk()
    love.load({})
end

local function load_mod()
    local mod_path = join_path(stub.state.mod_root, "balatrobot.lua")
    local chunk, err = loadfile(mod_path)
    if not chunk then
        error("Could not load balatrobot.lua: " .. tostring(err))
    end

    chunk()
end

local function tick_forever()
    while not stub.state.quit_requested do
        stub.advance(FIXED_DT)
        love.update(FIXED_DT)
    end
end

local ok, err = pcall(function()
    boot_game()
    load_mod()
    tick_forever()
end)

if not ok then
    io.stderr:write(tostring(err), "\n")
    shutdown(1)
end

shutdown(0)
