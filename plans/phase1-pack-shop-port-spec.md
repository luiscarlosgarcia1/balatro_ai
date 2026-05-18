# Phase 1 Pack/Shop Port Spec

Authority:
- `balatro_unpacked/game.lua`
- `balatro_unpacked/card.lua`
- `balatro_unpacked/functions/common_events.lua`
- `balatro_unpacked/functions/UI_definitions.lua`
- `balatro_unpacked/functions/button_callbacks.lua`
- `balatro_unpacked/functions/state_events.lua`
- `balatrobot/src/lua/endpoints/buy.lua`
- `balatrobot/src/lua/endpoints/pack.lua`
- `balatrobot/tests/lua/endpoints/test_pack.py`
- `balatrobot/tests/lua/endpoints/test_skip.py`

## 1. Real pack catalog to port

Implement shop boosters from `G.P_CENTERS` instead of the current synthetic names:

| Family | Variant | Keys | Cost | Contents (`extra`) | Picks (`choose`) | Weight |
| --- | --- | --- | --- | --- | --- | --- |
| Arcana | Normal | `p_arcana_normal_1..4` | 4 | 3 | 1 | 1 |
| Arcana | Jumbo | `p_arcana_jumbo_1..2` | 6 | 5 | 1 | 1 |
| Arcana | Mega | `p_arcana_mega_1..2` | 8 | 5 | 2 | 0.25 |
| Celestial | Normal | `p_celestial_normal_1..4` | 4 | 3 | 1 | 1 |
| Celestial | Jumbo | `p_celestial_jumbo_1..2` | 6 | 5 | 1 | 1 |
| Celestial | Mega | `p_celestial_mega_1..2` | 8 | 5 | 2 | 0.25 |
| Standard | Normal | `p_standard_normal_1..4` | 4 | 3 | 1 | 1 |
| Standard | Jumbo | `p_standard_jumbo_1..2` | 6 | 5 | 1 | 1 |
| Standard | Mega | `p_standard_mega_1..2` | 8 | 5 | 2 | 0.25 |
| Buffoon | Normal | `p_buffoon_normal_1..2` | 4 | 2 | 1 | 0.6 |
| Buffoon | Jumbo | `p_buffoon_jumbo_1` | 6 | 4 | 1 | 0.6 |
| Buffoon | Mega | `p_buffoon_mega_1` | 8 | 4 | 2 | 0.15 |
| Spectral | Normal | `p_spectral_normal_1..2` | 4 | 2 | 1 | 0.3 |
| Spectral | Jumbo | `p_spectral_jumbo_1` | 6 | 4 | 1 | 0.3 |
| Spectral | Mega | `p_spectral_mega_1` | 8 | 4 | 2 | 0.07 |

Use pack key as the primary identity, not display name.

## 2. Shop population flow to port

Per new shop:
- Base shop has `joker_max = 2`, one voucher slot, two booster slots.
- Fill jokers first by calling a weighted shop-card generator.
- Fill exactly one voucher using `current_round.voucher`.
- Fill exactly two boosters from `current_round.used_packs[1..2]`.

Rules:
- `get_pack('shop_pack')` picks from booster pool by weight, except first ever shop forces a Buffoon pack if `p_buffoon_normal_1` is not banned.
- Voucher comes from `get_next_voucher_key()`, which excludes already-used vouchers, vouchers already in shop, and vouchers whose `requires` chain is not yet satisfied.
- Booster slots persist as keys in `current_round.used_packs`; buying a booster marks that slot as `'USED'` and the slot stays empty for the rest of the shop.
- Reroll only refreshes joker/shop-card slots. It does not replace the voucher or booster slots.
- Tag hooks exist in Lua (`store_joker_create`, `store_joker_modify`, `voucher_add`, `shop_final_pass`) but Phase 1 can leave tag mutation unported if the hook points are preserved in Python.

## 3. Shop-card generator by family

Replace the current hardcoded inventory mix with Lua rates:
- Base rates: `joker_rate=20`, `tarot_rate=4`, `planet_rate=4`, `spectral_rate=0`, `playing_card_rate=0`.
- Generator chooses one shop card from weighted buckets: `Joker`, `Tarot`, `Planet`, `Base/Enhanced playing card`, `Spectral`.
- `Tarot`/`Planet`/`Spectral`/`Joker` use their real current pools via `get_current_pool(...)`.
- `Base` and `Enhanced` create a real playing card; `Enhanced` is only possible when the card-type bucket resolves that way.
- Joker shop cards can roll edition/perishable/rental/eternal through `create_card(...)`; Phase 1 should preserve edition support at minimum, and keep extension points for stickers.

Voucher-confirmed modifiers affecting shop-card generation:
- `Overstock`, `Overstock Plus`: `change_shop_size(+1)` each; practical limits become 3 then 4 joker/shop-card slots.
- `Tarot Merchant`, `Tarot Tycoon`: set `tarot_rate = 4 * extra`, giving rates 9.6 and 32.
- `Planet Merchant`, `Planet Tycoon`: set `planet_rate = 4 * extra`, giving rates 9.6 and 32.
- `Magic Trick`, `Illusion`: set `playing_card_rate = extra`, giving rate 4.
- `Hone`, `Glow Up`: set `edition_rate = extra`, giving 2x then 4x edition odds for edition polling.
- `Clearance Sale`, `Liquidation`: set `discount_percent` to 25 / 50 and recompute card costs.
- `Reroll Surplus`, `Reroll Glut`: subtract 2 each from base reroll cost and current reroll cost.

Phase 1 note:
- `Illusion` also modifies shop playing cards after generation: 40% chance to generate `Enhanced` instead of `Base`, then independent edition roll on some shop playing cards. Port that path together with shop-card generation.

## 4. Booster content generation by family

Arcana:
- Generate `extra` consumables.
- Default type is Tarot.
- If `v_omen_globe` is owned and `pseudorandom('omen_globe') > 0.8`, generate Spectral instead.

Celestial:
- Generate `extra` Planets.
- If `v_telescope` is owned, force slot 1 to the Planet for the most-played visible poker hand.
- Remaining slots are normal Planet pool draws.

Spectral:
- Generate `extra` Spectral consumables.

Buffoon:
- Generate `extra` Jokers.
- Use the same Joker creation path as shop/pack creation, so edition and shop sticker logic stay consistent.

Standard:
- Generate `extra` playing cards.
- Card type is `Enhanced` if `pseudorandom('stdset'..ante) > 0.6`, else `Base`.
- After creation, poll edition with guaranteed-standard path `poll_edition(..., edition_rate=2, guaranteed=true)`.
- Independently poll seal with `seal_rate = 10`; on success assign one of `Red/Blue/Gold/Purple`.

Special pool behavior confirmed by Lua:
- `create_card` may force `c_soul` into Tarot/Spectral/Tarot_Planet pools on a very small roll.
- `create_card` may force `c_black_hole` into Planet/Spectral pools on a very small roll.
- `get_current_pool('Planet')` excludes softlocked planets whose hand has never been played.
- `Black Hole` and `The Soul` are otherwise excluded from normal pool assembly.

## 5. Pack open / multi-pick / skip behavior

On booster purchase:
- Deduct cost.
- Mark the booster slot `USED`.
- Open pack and set `pack_size = extra`, `pack_choices = choose`.
- Transition to pack-open phase.

Selection behavior:
- Normal and Jumbo packs close after one valid selection.
- Mega packs keep the pack open after the first valid selection and decrement `pack_choices` from 2 to 1.
- Second valid selection closes the pack and returns to shop.
- After a selection, remaining pack cards stay in order except for the removed card; tests rely on shifted indices.

Skip behavior:
- `skip_booster` is legal for open packs and immediately closes the pack, returns to shop, and fires `skipping_booster` joker hooks.
- Skip does not consume remaining picks one by one; it aborts the whole pack.

Pack validation confirmed by `balatrobot`:
- Buffoon selection must fail if joker slots are full.
- Consumables must enforce target counts from `G.P_CENTERS`, with special cases:
  - `c_aura`: exactly 1 target.
  - `c_ankh`: requires at least 1 joker, not hand-card targets.
- Pack skip/selection only exists in booster-open state.

## 6. Blind skip behavior confirmed

Blind skip is separate from pack skip:
- Small blind skip marks Small `SKIPPED` and promotes Big to `SELECT`.
- Big blind skip marks Big `SKIPPED` and promotes Boss to `SELECT`.
- Boss blind cannot be skipped.
- Skip increments `G.GAME.skips`, applies the current tag immediately, and fires `skip_blind` joker hooks.

Phase 1 should not merge this into shop logic, but should keep pack skip and blind skip semantics distinct in handlers and observations.

## 7. Python modules/functions to update

Primary port targets:
- `balatro-gym/balatro_gym/core/shop.py`
  - Replace `COST_TABLE`, `VOUCHER_EFFECTS`, `ShopItem`, `Shop._generate_inventory`, `Shop._open_pack`, `Shop.step`.
  - Add real data tables for voucher centers and booster centers.
  - Add helpers mirroring Lua: `get_current_pool`, `get_pack`, `create_card_for_shop`, `create_booster_contents`, `calculate_reroll_cost`, `apply_voucher_effect`.
- `balatro-gym/balatro_gym/core_utils/phase_handlers/shop_phase.py`
  - Update `generate_shop`, `_handle_buy_item`, `_handle_reroll`, `_process_purchase`.
  - Booster purchase must open pack state instead of directly granting cards.
  - Reroll must refresh only joker/shop-card slots.
- `balatro-gym/balatro_gym/core_utils/phase_handlers/pack_open.py`
  - Replace `open_pack`, `_get_cards_to_select`, `_handle_select_card`, `_handle_skip_pack`, `_complete_pack_opening`, `_apply_pack_item`.
  - Track `pack_key`, `pack_choices_remaining`, and real pack-card objects.
- `balatro-gym/balatro_gym/core_utils/state.py`
  - Add shop/pack fields: `used_vouchers`, `shop_joker_slots`, `current_voucher_key`, `current_round_used_packs`, `free_rerolls`, `reroll_cost_increase`, `pack_key`, `pack_choices`, `pack_size`, pack contents metadata, `discount_percent`, `edition_rate`, `joker_rate`, `tarot_rate`, `planet_rate`, `spectral_rate`, `playing_card_rate`.
- `balatro-gym/balatro_gym/core_utils/action_handler.py`
  - Enable pack-open action masks.
  - In shop phase, gate buy actions by slot-specific validity, not only affordability.
- `balatro-gym/balatro_gym/core_utils/observation_builder.py`
  - Expose pack-open observations and separate enough shop metadata to distinguish joker/shop-card vs voucher vs booster slots.
- `balatro-gym/balatro_gym/core/constants.py`
  - Keep action ids stable but rename/align pack constants if needed (`SELECT_FROM_PACK_BASE`, `SKIP_PACK`) so handlers and masks match.

Do not spend Phase 1 effort on legacy alternate envs (`balatro_env.py`, `balatro_env_2.py`, `balatro_env_v2.py`) beyond keeping imports compiling. Port the maintained core path first.

## 8. Acceptance checks for Phase 1

Match these externally visible outcomes:
- New shop: 2 joker/shop-card slots by default, 1 voucher, 2 boosters.
- `Overstock` / `Overstock Plus` increase only joker/shop-card slots.
- Voucher slot does not reroll.
- Booster slots do not reroll.
- Bought booster disappears permanently for that shop.
- Mega booster allows exactly 2 picks, then closes.
- Pack skip closes immediately and returns to shop.
- Celestial pack with Telescope forces first card to the most-played-hand planet.
- Standard pack cards can carry editions and seals.
- Reroll cost starts from base, respects free rerolls, and increments by +1 per paid reroll after modifiers.
