local readiness = dofile("mods/live_state_exporter/state/readiness.lua")

local function eq(a, b, msg)
  if a ~= b then
    error(msg or ("expected " .. tostring(b) .. ", got " .. tostring(a)), 2)
  end
end

eq(readiness.is_ready(nil), false, "missing root should not be ready")
eq(readiness.is_ready({}), false, "missing controller and game should not be ready")
eq(readiness.is_ready({ CONTROLLER = {}, GAME = {} }), true, "baseline controller gates should be ready")
eq(readiness.is_ready({ CONTROLLER = { locked = true }, GAME = {} }), false, "locked controller should block readiness")
eq(
  readiness.is_ready({ CONTROLLER = { interrupt = { focus = true } }, GAME = {} }),
  false,
  "interrupt focus should block readiness"
)
eq(
  readiness.is_ready({ CONTROLLER = {}, GAME = { STOP_USE = 1 } }),
  false,
  "STOP_USE should block readiness"
)
eq(
  readiness.is_ready({ CONTROLLER = {}, GAME = { STOP_USE = "0" } }),
  true,
  "numeric STOP_USE strings should still pass readiness"
)
