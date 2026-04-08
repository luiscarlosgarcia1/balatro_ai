-- Minimal JSON decoder for ai/action.json parsing.
-- Handles: objects, arrays, strings (with escape sequences),
--          numbers, booleans, and null.

local M = {}

-- ============================================================
-- Internal parser
-- ============================================================

local parse_value  -- forward declaration

local function skip_ws(s, i)
  while i <= #s do
    local c = s:sub(i, i)
    if c == ' ' or c == '\t' or c == '\n' or c == '\r' then
      i = i + 1
    else
      break
    end
  end
  return i
end

local function parse_string(s, i)
  -- i points at the opening "
  i = i + 1
  local buf = {}
  while i <= #s do
    local c = s:sub(i, i)
    if c == '"' then
      return table.concat(buf), i + 1
    elseif c == '\\' then
      i = i + 1
      local e = s:sub(i, i)
      if     e == '"'  then buf[#buf+1] = '"'
      elseif e == '\\' then buf[#buf+1] = '\\'
      elseif e == '/'  then buf[#buf+1] = '/'
      elseif e == 'n'  then buf[#buf+1] = '\n'
      elseif e == 'r'  then buf[#buf+1] = '\r'
      elseif e == 't'  then buf[#buf+1] = '\t'
      elseif e == 'b'  then buf[#buf+1] = '\b'
      elseif e == 'f'  then buf[#buf+1] = '\f'
      elseif e == 'u'  then
        local hex = s:sub(i + 1, i + 4)
        local cp  = tonumber(hex, 16)
        if cp then
          if cp < 0x80 then
            buf[#buf+1] = string.char(cp)
          elseif cp < 0x800 then
            buf[#buf+1] = string.char(0xC0 + math.floor(cp / 64),
                                       0x80 + (cp % 64))
          else
            buf[#buf+1] = string.char(0xE0 + math.floor(cp / 4096),
                                       0x80 + math.floor((cp % 4096) / 64),
                                       0x80 + (cp % 64))
          end
        end
        i = i + 4
      end
      i = i + 1
    else
      buf[#buf+1] = c
      i = i + 1
    end
  end
  error("json: unterminated string")
end

local function parse_number(s, i)
  local j = i
  if s:sub(j, j) == '-' then j = j + 1 end
  while j <= #s and s:sub(j, j):match('%d') do j = j + 1 end
  if j <= #s and s:sub(j, j) == '.' then
    j = j + 1
    while j <= #s and s:sub(j, j):match('%d') do j = j + 1 end
  end
  if j <= #s and s:sub(j, j):match('[eE]') then
    j = j + 1
    if j <= #s and s:sub(j, j):match('[+-]') then j = j + 1 end
    while j <= #s and s:sub(j, j):match('%d') do j = j + 1 end
  end
  local num = tonumber(s:sub(i, j - 1))
  assert(num, "json: invalid number at position " .. i)
  return num, j
end

local function parse_array(s, i)
  i = i + 1  -- skip '['
  local arr = {}
  i = skip_ws(s, i)
  if s:sub(i, i) == ']' then return arr, i + 1 end
  while true do
    local val
    val, i = parse_value(s, i)
    arr[#arr + 1] = val
    i = skip_ws(s, i)
    local c = s:sub(i, i)
    if c == ']' then return arr, i + 1 end
    assert(c == ',', "json: expected ',' or ']' at position " .. i)
    i = skip_ws(s, i + 1)
  end
end

local function parse_object(s, i)
  i = i + 1  -- skip '{'
  local obj = {}
  i = skip_ws(s, i)
  if s:sub(i, i) == '}' then return obj, i + 1 end
  while true do
    assert(s:sub(i, i) == '"', "json: expected '\"' at position " .. i)
    local key
    key, i = parse_string(s, i)
    i = skip_ws(s, i)
    assert(s:sub(i, i) == ':', "json: expected ':' at position " .. i)
    i = skip_ws(s, i + 1)
    local val
    val, i = parse_value(s, i)
    obj[key] = val
    i = skip_ws(s, i)
    local c = s:sub(i, i)
    if c == '}' then return obj, i + 1 end
    assert(c == ',', "json: expected ',' or '}' at position " .. i)
    i = skip_ws(s, i + 1)
  end
end

parse_value = function(s, i)
  i = skip_ws(s, i)
  local c = s:sub(i, i)
  if c == '"' then
    return parse_string(s, i)
  elseif c == '{' then
    return parse_object(s, i)
  elseif c == '[' then
    return parse_array(s, i)
  elseif c == 't' then
    assert(s:sub(i, i + 3) == 'true',  "json: expected 'true' at position "  .. i)
    return true, i + 4
  elseif c == 'f' then
    assert(s:sub(i, i + 4) == 'false', "json: expected 'false' at position " .. i)
    return false, i + 5
  elseif c == 'n' then
    assert(s:sub(i, i + 3) == 'null',  "json: expected 'null' at position "  .. i)
    return nil, i + 4
  elseif c == '-' or c:match('%d') then
    return parse_number(s, i)
  else
    error("json: unexpected character '" .. c .. "' at position " .. i)
  end
end

-- ============================================================
-- Public API
-- ============================================================

function M.decode(s)
  assert(type(s) == 'string', 'json.decode: expected string, got ' .. type(s))
  local val = parse_value(s, 1)
  return val
end

return M
