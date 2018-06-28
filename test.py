from multiworld.envs.mujoco.sawyer_xyz.sawyer_pick_and_place \
        import SawyerPickAndPlaceEnv, SawyerPickAndPlaceEnvYZ
import time
import numpy as np

env = SawyerPickAndPlaceEnvYZ(hide_arm=True, hide_goal_markers=True)
env.reset()
env.render()
while True:

    # delta = np.array([0.0, -.2, -1.0])
    # for _ in range(85):
        # env.step(delta)
        # env.render()
    # delta = np.array([0.0, 0, 1.0])
    # for _ in range(30):
        # env.step(delta)
        # env.render()
    # delta = np.array([0.0, .2, 1.0])
    # for _ in range(130):
        # env.step(delta)
        # env.render()

    env.set_to_goal(env.sample_goal())
