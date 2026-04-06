local out = {}

local dir = "ai"
local path = dir .. "/live_state.json"

local function is_array(value)
  if type(value) ~= "table" then
    return false
  end
  local meta = getmetatable(value)
  if meta and meta.__ls_arr == true then
    return true
  end
  local item_count = #value
  if item_count == 0 then
    return false
  end
  for key, _ in pairs(value) do
    if type(key) ~= "number" or key < 1 or key > item_count or key % 1 ~= 0 then
      return false
    end
  end
  return true
end

local function is_null_value(value)
  if type(value) ~= "table" then
    return false
  end
  local meta = getmetatable(value)
  return meta and meta.__ls_null == true or false
end

local function escape_json(value)
  local map = {
    ['\\'] = '\\\\',
    ['"'] = '\\"',
    ['\b'] = '\\b',
    ['\f'] = '\\f',
    ['\n'] = '\\n',
    ['\r'] = '\\r',
    ['\t'] = '\\t',
  }

  return value:gsub('[%z\1-\31\\"]', function(char)
    return map[char] or string.format("\\u%04x", char:byte())
  end)
end

local function encode_value(value, seen)
  local kind = type(value)
  if kind == "nil" then
    return "null"
  end
  if kind == "boolean" then
    return value and "true" or "false"
  end
  if kind == "number" then
    if value ~= value or value == math.huge or value == -math.huge then
      return "null"
    end
    return tostring(value)
  end
  if kind == "string" then
    return '"' .. escape_json(value) .. '"'
  end
  if kind ~= "table" or is_null_value(value) then
    return "null"
  end

  seen = seen or {}
  if seen[value] then
    return "null"
  end
  seen[value] = true

  local parts = {}
  if is_array(value) then
    for i = 1, #value do
      parts[#parts + 1] = encode_value(value[i], seen)
    end
    seen[value] = nil
    return "[" .. table.concat(parts, ",") .. "]"
  end

  local keys = {}
  for key, _ in pairs(value) do
    keys[#keys + 1] = key
  end
  table.sort(keys, function(left, right)
    return tostring(left) < tostring(right)
  end)

  for i = 1, #keys do
    local key = keys[i]
    parts[#parts + 1] = '"' .. escape_json(tostring(key)) .. '":' .. encode_value(value[key], seen)
  end
  seen[value] = nil
  return "{" .. table.concat(parts, ",") .. "}"
end

function out.path()
  return path
end

function out.encode_json(value)
  return encode_value(value)
end

function out.make_signature(value)
  return encode_value(value)
end

function out.write_snapshot(body)
  local love = rawget(_G, "love")
  local filesystem = love and love.filesystem
  if type(filesystem) ~= "table" then
    return false
  end
  if type(filesystem.createDirectory) == "function" then
    local ok = pcall(filesystem.createDirectory, dir)
    if not ok then
      return false
    end
  end
  if type(filesystem.write) ~= "function" then
    return false
  end
  local ok = pcall(filesystem.write, path, body)
  return ok
end

function out.new_exporter(options)
  options = type(options) == "table" and options or {}

  local exporter = {
    dt = options.dt or 0.05,
    now = options.now,
    read_state = options.read_state,
    build_shell = options.build_shell,
    make_signature = options.make_signature or out.make_signature,
    encode_json = options.encode_json or out.encode_json,
    write_snapshot = options.write_snapshot or out.write_snapshot,
    last_write_at = nil,
    last_signature = nil,
  }

  function exporter:tick()
    local now = self.now and self.now() or 0
    if self.last_write_at ~= nil and (now - self.last_write_at) < self.dt then
      return false
    end

    local ok_read, raw_state = pcall(function()
      return self.read_state and self.read_state() or {}
    end)
    if not ok_read then
      return false
    end

    local ok_build, payload = pcall(function()
      return self.build_shell and self.build_shell(raw_state) or raw_state
    end)
    if not ok_build then
      return false
    end

    local ok_signature, signature = pcall(function()
      return self.make_signature(payload)
    end)
    if not ok_signature then
      return false
    end
    if signature == self.last_signature then
      return false
    end

    local ok_encode, body = pcall(function()
      return self.encode_json(payload)
    end)
    if not ok_encode then
      return false
    end

    local ok_write, wrote = pcall(function()
      return self.write_snapshot(body)
    end)
    if not ok_write or not wrote then
      return false
    end

    self.last_write_at = now
    self.last_signature = signature
    return true
  end

  return exporter
end

return out
