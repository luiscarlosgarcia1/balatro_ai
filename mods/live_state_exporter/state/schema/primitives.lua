-- Schema sentinels and small cloning/default helpers.
return function(values)
  local primitives = {}

  local as_table = values.as_table

  local array_meta = { __ls_arr = true }
  local null_value = setmetatable({}, { __ls_null = true })

  function primitives.mark_array(value)
    return setmetatable(value, array_meta)
  end

  function primitives.clone_array(source)
    local out = {}
    if type(source) == "table" then
      for i = 1, #source do
        out[i] = source[i]
      end
    end
    return primitives.mark_array(out)
  end

  function primitives.clone_mapped_array(source, map_fn)
    local out = {}
    if type(source) == "table" then
      for i = 1, #source do
        out[i] = map_fn(as_table(source[i]) or {})
      end
    end
    return primitives.mark_array(out)
  end

  function primitives.required_or(value, default)
    if value == nil then
      return default
    end
    return value
  end

  function primitives.optional_or_null(value)
    if value == nil then
      return null_value
    end
    return value
  end

  function primitives.is_array(value)
    local meta = getmetatable(value)
    return meta and meta.__ls_arr == true or false
  end

  function primitives.is_null(value)
    local meta = getmetatable(value)
    return meta and meta.__ls_null == true or false
  end

  return primitives
end
