from multiworld.envs.mujoco.sawyer_xyz.sawyer_pick_and_place \
        import SawyerPickAndPlaceEnv, SawyerPickAndPlaceEnvYZ
import time
import numpy as np

env = SawyerPickAndPlaceEnvYZ(hide_arm=True, hide_goal_markers=True, action_scale=.02)
env.reset()
env.render()
while True:

    delta = np.array([-1, -1, 1.0])
    for _ in range(10):
        env.step(delta)
        env.render()
    delta = np.array([0.0, .2, 1.0])
    for _ in range(3):
        env.step(delta)
        env.render()
    delta = np.array([-1.0, 0.0, 1.0])
    for _ in range(55):
        env.step(delta)
        env.render()
    print(env.get_endeff_pos())
    env.reset()
#    env.set_to_goal(env.sample_goal())
