## Setup

**Dependencies** (one-time):
```bash
brew install python@3.12 poetry
cd balatro-gym
poetry env use python3.12
eval $(poetry env activate)
pip install stable-baselines3 torch tensorboard tqdm rich
pip install -e /path/to/balatro_ai/stable-baselines3-contrib
```

## Training

**Activate venv** (every terminal session):
```bash
eval $(poetry env activate)
```

**Start training** (auto-resumes from `final_model.zip` if it exists):
```bash
python3 train_balatro_fixed.py --timesteps 1000000
```

**Monitor training** (second terminal):
```bash
tensorboard --logdir run_balatro_fixed/tb_logs
# open http://localhost:6006
```

**Stop training**: `Ctrl+C` — saves to `run_balatro_fixed/final_model.zip` automatically

Checkpoints saved to `run_balatro_fixed/checkpoints/` every 500k steps.

---

## Credits

- [stable-baselines3-contrib](https://github.com/Stable-Baselines-Team/stable-baselines3-contrib) — contributed RL algorithm implementations used for training
- [balatro-gym](https://github.com/cassiusfive/balatro-gym) — OpenAI Gym environment for Balatro
- [balatrobot](https://github.com/coder/balatrobot) — headless Balatro bot framework
