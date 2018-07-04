from multiworld.envs.mujoco.sawyer_xyz.sawyer_pick_and_place \
        import SawyerPickAndPlaceEnv, SawyerPickAndPlaceEnvYZ
import time
import numpy as np

env = SawyerPickAndPlaceEnvYZ(
    hide_arm=True,
    hide_goal_markers=True,
 #   obj_init_positions=((0, 0.575, 0.02),(0, 0.625, 0.02)),
)
env.reset()
env.render()
for i in range(1000):
    print(i)
    env.reset()
#    env.put_obj_in_hand()
#    delta = env.action_space.sample()#np.array([0.0, -1.0, -1.0])
#    for _ in range(10):
#        delta[2] = 1
#        env.step(delta)
    """hand_pos = env.sample_hand_pos(1)[0]
    env._move_hand(hand_pos, -1)
    env.put_obj_in_hand()
    obs = env._get_obs()
    env.render()
    env.reset()"""
    env.set_to_goal(env.sample_goal())
    env.render()
    # action = np.array([0.0, -.5, -1])#env.action_space.sample()
    # for _ in range(140):
        # env.step(action)
        # env.render()
    # action = np.array([0.0, 0.1, 1])#env.action_space.sample()
    # for _ in range(140):
        # env.step(action)
        # env.render()

    # print(env._get_obs())

    """
    delta = np.array([0.0, 0.0, 1.0])
    for _ in range(20):
        env.step(delta)
        env.render()
    delta = np.array([0.0, .6, 1.0])
    for _ in range(250):
        env.step(delta)
        env.render()

    env.reset()"""
