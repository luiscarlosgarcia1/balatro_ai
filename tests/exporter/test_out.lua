local schema = dofile("mods/live_state_exporter/state/schema.lua")
local out = dofile("mods/live_state_exporter/out.lua")

local function eq(a, b, msg)
  if a ~= b then
    error(msg or ("expected " .. tostring(b) .. ", got " .. tostring(a)), 2)
  end
end

local function ne(a, b, msg)
  if a == b then
    error(msg or "expected values to differ", 2)
  end
end

local function ok(v, msg)
  if not v then
    error(msg or "expected truthy value", 2)
  end
end

local function has(s, part, msg)
  ok(string.find(s, part, 1, true) ~= nil, msg or ("missing fragment: " .. part))
end

local a = schema.build_shell({
  state_id = 1,
  dollars = 4,
  score = { current = 25, target = 300 },
})
local b = schema.build_shell({
  state_id = 1,
  dollars = 4,
  score = { current = 25, target = 300 },
})
local c = schema.build_shell({
  state_id = 1,
  dollars = 5,
  score = { current = 25, target = 300 },
})

local ea = out.encode_json(a)
local eb = out.encode_json(b)
ok(ea == eb, "encoder should be deterministic for identical payloads")
has(ea, '"deck_key":null', "encoder should emit null for optional fields")
has(ea, '"blinds":[]', "encoder should emit [] for empty arrays")
has(ea, '"score":{"current":25,"target":300}', "encoder should emit nested objects")
eq(out.make_signature(a), out.make_signature(b), "identical payloads should have the same signature")
ne(out.make_signature(a), out.make_signature(c), "meaningful payload changes should alter the signature")

local t = 0
local dollars = 4
local writes = {}
local ex = out.new_exporter({
  dt = 0.05,
  now = function()
    return t
  end,
  read_state = function()
    return {
      dollars = dollars,
      score = { current = 25, target = 300 },
    }
  end,
  build_shell = schema.build_shell,
  write_snapshot = function(body)
    writes[#writes + 1] = body
    return true
  end,
})

eq(ex:tick(), true, "first eligible tick should write")
eq(#writes, 1, "first tick should produce one write")
t = 0.02
eq(ex:tick(), false, "sub-interval tick should not write")
eq(#writes, 1, "sub-interval tick should not add writes")
t = 0.10
eq(ex:tick(), false, "unchanged payload should not write after interval")
eq(#writes, 1, "unchanged payload should still be deduped")
dollars = 5
t = 0.16
eq(ex:tick(), true, "changed payload should write after interval")
eq(#writes, 2, "changed payload should add a write")

local ready_t = 0
local ready_dollars = 7
local ready_writes = {}
local ready_reads = 0
local ready_builds = 0
local ready_flag = false
local ready_exporter = out.new_exporter({
  dt = 0.05,
  now = function()
    return ready_t
  end,
  is_ready = function()
    return ready_flag
  end,
  read_state = function()
    ready_reads = ready_reads + 1
    return {
      dollars = ready_dollars,
      score = { current = 25, target = 300 },
    }
  end,
  build_shell = function(raw_state)
    ready_builds = ready_builds + 1
    return schema.build_shell(raw_state)
  end,
  write_snapshot = function(body)
    ready_writes[#ready_writes + 1] = body
    return true
  end,
})

eq(ready_exporter:tick(), true, "startup tick should bypass readiness and write once")
eq(#ready_writes, 1, "startup bypass should still write a canonical snapshot")
eq(ready_reads, 1, "startup bypass should still read state")
eq(ready_builds, 1, "startup bypass should still build the payload")

ready_t = 0.06
eq(ready_exporter:tick(), false, "readiness false should block later writes")
eq(#ready_writes, 1, "readiness false should not add writes after startup")
eq(ready_reads, 1, "readiness false should skip full state reads")
eq(ready_builds, 1, "readiness false should skip payload builds")

ready_flag = true
ready_t = 0.12
eq(ready_exporter:tick(), false, "identical ready payload should still be deduped")
eq(#ready_writes, 1, "deduped ready payload should not write")
eq(ready_reads, 2, "ready tick should resume state reads")
eq(ready_builds, 2, "ready tick should resume payload builds")

ready_dollars = 8
ready_t = 0.18
eq(ready_exporter:tick(), true, "changed ready payload should write")
eq(#ready_writes, 2, "changed ready payload should add a write")

local startup_retry_t = 0
local startup_retry_writes = 0
local startup_retry_reads = 0
local startup_retry_flag = false
local startup_retry_exporter = out.new_exporter({
  dt = 0.05,
  now = function()
    return startup_retry_t
  end,
  is_ready = function()
    return startup_retry_flag
  end,
  read_state = function()
    startup_retry_reads = startup_retry_reads + 1
    return {
      dollars = 11,
      score = { current = 25, target = 300 },
    }
  end,
  build_shell = schema.build_shell,
  write_snapshot = function(_)
    startup_retry_writes = startup_retry_writes + 1
    return startup_retry_writes > 1
  end,
})

eq(startup_retry_exporter:tick(), false, "failed startup write should report no write")
eq(startup_retry_writes, 1, "failed startup write should still attempt the write")
eq(startup_retry_reads, 1, "failed startup write should still read state")

startup_retry_t = 0.01
eq(startup_retry_exporter:tick(), false, "failed startup write should still respect the read cadence before retrying")
eq(startup_retry_writes, 1, "sub-cadence retry should not attempt another startup write yet")
eq(startup_retry_reads, 1, "sub-cadence retry should not perform another read yet")
ok(not startup_retry_exporter.has_written_once, "startup write should stay incomplete until a successful retry")

startup_retry_t = 0.06
eq(startup_retry_exporter:tick(), true, "failed startup write should retry on the next read slot")
eq(startup_retry_writes, 2, "retry should attempt another startup write")
eq(startup_retry_reads, 2, "retry should still bypass readiness until first success")
ok(startup_retry_exporter.has_written_once, "successful retry should mark startup write complete")

local read_fail_writes = {}
local read_fail_exporter = out.new_exporter({
  now = function()
    return 0
  end,
  read_state = function()
    error("boom from read_state")
  end,
  build_shell = schema.build_shell,
  write_snapshot = function(body)
    read_fail_writes[#read_fail_writes + 1] = body
    return true
  end,
})

local ok_tick, tick_result = pcall(function()
  return read_fail_exporter:tick()
end)

ok(ok_tick, "tick should not bubble read_state failures")
eq(tick_result, false, "tick should report no write on read_state failure")
eq(#read_fail_writes, 0, "read_state failure should not write a snapshot")

local unstable_t = 0
local unstable_writes = {}
local unstable_builds = 0
local unstable_exporter = out.new_exporter({
  dt = 0.05,
  now = function()
    return unstable_t
  end,
  read_state = function()
    return {
      state_id = 3,
      dollars = 9,
      score = { current = 10, target = 100 },
    }
  end,
  build_shell = function(raw)
    unstable_builds = unstable_builds + 1
    if unstable_builds == 1 then
      error("boom from build_shell")
    end
    return schema.build_shell(raw)
  end,
  write_snapshot = function(body)
    unstable_writes[#unstable_writes + 1] = body
    return true
  end,
})

local unstable_ok, unstable_first = pcall(function()
  return unstable_exporter:tick()
end)

ok(unstable_ok, "tick should not bubble build_shell failures")
eq(unstable_first, false, "failed build_shell should skip writes")
eq(#unstable_writes, 0, "build_shell failure should not write a snapshot")

unstable_t = 0.06
eq(unstable_exporter:tick(), true, "exporter should retry after build_shell failure")
eq(#unstable_writes, 1, "successful retry should write exactly once")
