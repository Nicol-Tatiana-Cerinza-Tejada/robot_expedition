"""Entrenamiento PPO opcional: pip install stable-baselines3 torch."""
from robot_expedition import RobotExpeditionEnv

try:
    from stable_baselines3 import PPO
except ImportError as exc:
    raise SystemExit("Instala el extra de entrenamiento: pip install stable-baselines3 torch") from exc

env = RobotExpeditionEnv()
model = PPO("MlpPolicy", env, verbose=1, tensorboard_log="logs/ppo")
model.learn(total_timesteps=100_000)
model.save("models/robot_expedition_ppo")
env.close()
