import math

import numpy as np

from robot_expedition import BeaconExpeditionEnv
from robot_expedition.envs.beacon_expedition import BASE, BEACONS, BLOCK


def place(env, x, y, theta=0.0):
    env.set_pose(x, y, theta, speed=0.6)


def test_all_levels_reset_and_step_with_same_contract():
    observations = []
    for level in ("n1", "n2", "n3"):
        env = BeaconExpeditionEnv(level=level)
        obs, _ = env.reset(seed=4)
        next_obs, _, _, _, _ = env.step(0)
        observations.extend((obs, next_obs))
        assert obs.shape == (20,)
        assert env.action_space.n == 5
    assert all(item.shape == observations[0].shape for item in observations)


def test_n1_success_after_b1_and_base():
    env = BeaconExpeditionEnv(level="n1", ray_noise=0.0)
    env.reset(seed=1)
    place(env, BEACONS[0][0] - 0.7, BEACONS[0][1])
    _, _, terminated, _, info = env.step(0)
    assert info["stage"] == 3 and not terminated        # etapa 3 = volver a la base en todo nivel
    assert env.target() == BASE[:2]
    place(env, BASE[0] + BASE[2] + 0.2, BASE[1], math.pi)
    _, _, terminated, _, info = env.step(0)
    assert terminated and info["success"] and info["end"] == "exito"


def test_n3_activates_block_and_dead_ray_degrades_sensor():
    env = BeaconExpeditionEnv(level="n3")
    env.reset(seed=2)
    place(env, BEACONS[0][0] - 0.7, BEACONS[0][1])
    env.step(0)
    assert env.block_active and BLOCK[1:] in env.obstacles()
    rays = env.rays()
    assert rays[4] == 5.0
    assert env.ray_noise == 0.08


def test_level_rocks_match_physics_after_reset_and_jitter():
    # Antes reset() volvia a cargar las 5 rocas en la lista aunque N1 solo tiene 2 en MuJoCo.
    for jitter in (0.0, 0.5):
        env = BeaconExpeditionEnv(level="n1", rock_jitter=jitter)
        env.reset(seed=3)
        assert len(env.rocks) == len(env._rock_ids) == 2
        assert [r[0] for r in env.map_spec()["rocks"]] == ["R1", "R2"]
