local values = {}

function values.as_table(value)
  return type(value) == "table" and value or nil
end

function values.first_defined(...)
  for i = 1, select("#", ...) do
    local value = select(i, ...)
    if value ~= nil then
      return value
    end
  end
  return nil
end

function values.to_number(value)
  if type(value) == "number" then
    return value
  end
  if type(value) == "string" and value:match("^%-?%d+$") then
    return tonumber(value)
  end
  return nil
end

function values.lower_string(value)
  return type(value) == "string" and string.lower(value) or nil
end

function values.first_boolean(...)
  for i = 1, select("#", ...) do
    local value = select(i, ...)
    if type(value) == "boolean" then
      return value
    end
  end
  return nil
end

return values
