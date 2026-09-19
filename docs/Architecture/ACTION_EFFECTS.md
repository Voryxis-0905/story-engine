# Action effects bridge

`action_rules` may declare consequences that the engine commits after the
consistency checker passes. The planner and writer receive the normalized plan
as `action_resolution.engine_effects`; their text cannot add executable paths.

The turn order is:

1. Match an action rule and resolve capability, tools, access, and opposition.
2. Normalize declared consequences through the action-effects whitelist.
3. Give the normalized outcome to planner, writer, and consistency checker.
4. If the checker blocks the turn, commit nothing.
5. Apply normalized effects, advance the clock, then resolve world events.
6. Commit chapter, character state, world configuration, events, and receipt in
   the existing atomic world transaction.

## Supported consequences

```json
{"type":"world_flag_set","key":"seal_broken","value":true}
{"type":"world_flags_set","values":{"gate.open":true,"alarm":false}}
{"type":"knowledge_flag_add","character_id":"hero","flag":"knows_hidden_name"}
{"type":"status_effect_add","character_id":"hero","effect":{"name":"Marked","duration":3}}
{"type":"inventory_add","character_id":"hero","item":{"name":"Archive Key"}}
{"type":"inventory_remove","character_id":"hero","item":{"instance_id":"key_1"}}
{"type":"event_influence","event_id":"eclipse","key":"seal_broken","value":true}
{"type":"event_influence","event_id":"eclipse","key":"seal_broken","value":true,"outcome_id":"eclipse_prevented","visibility":"observable"}
```

`character_id` defaults to the protagonist. An `event_influence` writes an
auditable intervention record and exposes the value under
`world_flags.event_influence.<event_id>.<key>`. An optional valid `outcome_id`
locks the branch selected when that event eventually triggers; the event itself
still occurs on its own schedule.

Event influence is `hidden` by default. Its event ID, selected outcome, key, and
value are redacted from narrator and player-facing chapter data. Set
`visibility` to `observable` only when the viewpoint character can perceive the
causal link. Other effect types default to `observable` and may also be hidden.

Consequences apply to `success` by default. Use `apply_on` when another result
has a distinct cost:

```json
{
  "type": "status_effect_add",
  "effect": {"name": "Sprained wrist", "duration": 2},
  "apply_on": ["partial", "failure"]
}
```

Unknown effect types, arbitrary state paths, missing characters, terminal
events, and unknown event outcomes are recorded in `rejected_effects` and never
executed. Creator mode can replace `action_rules` through the previewable
`creator/edit` transaction using change kind `action_rules`.
