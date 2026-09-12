# Balatron glossary

## Watchable session

A locally launched, visible Balatro instance driven through BalatroBot while a
policy completes one seeded Red Deck / White Stake first Small Blind through
the Round Tactics boundary. Its public surface is both a CLI command and a
callable Python API. It reports a versioned JSON Lines lifecycle trace to
standard output, distinguishes a live bridge from a settled controllable
session, and cleans up its managed instance by default after the blind settles.
An explicit inspection mode may keep the window open until interruption.

## Round Tactics

The maintained, shop-free boundary for a seeded first Small Blind. It exposes
settled observations and canonical legal actions, and is driven by a policy.

## BalatroBot

The source of truth for launching and managing a real Balatro instance and for
its JSON-RPC game bridge.
