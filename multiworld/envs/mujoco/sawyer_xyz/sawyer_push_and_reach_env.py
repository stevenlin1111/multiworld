from collections import OrderedDict
import numpy as np
from gym.spaces import Box, Dict

from multiworld.envs.env_util import get_stat_in_paths, \
    create_stats_ordered_dict, get_asset_full_path
from multiworld.core.multitask_env import MultitaskEnv
from multiworld.envs.mujoco.sawyer_xyz.base import SawyerXYZEnv

import mujoco_py

class SawyerPushAndReachXYZEnv(MultitaskEnv, SawyerXYZEnv):
    def __init__(
            self,
            puck_low=(-.4, .2),
            puck_high=(.4, 1),

            reward_type='state_distance',
            norm_order=1,
            indicator_threshold=0.06,

            hand_low=(-0.28, 0.3, 0.05),
            hand_high=(0.28, 0.9, 0.3),

            fix_goal=False,
            fixed_goal=(0.15, 0.6, 0.02, -0.15, 0.6),
            goal_low=(-0.25, 0.3, 0.02, -.2, .4),
            goal_high=(0.25, 0.875, 0.02, .2, .8),

            hide_goal_markers=False,
            init_puck_z=0.02,

            reset_free=False,
            num_resets_before_puck_reset=1,
            **kwargs
    ):
        self.quick_init(locals())
        MultitaskEnv.__init__(self)
        SawyerXYZEnv.__init__(
            self,
            hand_low=hand_low,
            hand_high=hand_high,
            model_name=self.model_name,
            **kwargs
        )
        if puck_low is None:
            puck_low = self.hand_low[:2]
        if puck_high is None:
            puck_high = self.hand_high[:2]
        puck_low = np.array(puck_low)
        puck_high = np.array(puck_high)

        self.puck_low = puck_low
        self.puck_high = puck_high

        if goal_low is None:
            goal_low = np.hstack((self.hand_low, puck_low))
        if goal_high is None:
            goal_high = np.hstack((self.hand_high, puck_high))
        self.goal_low = np.array(goal_low)
        self.goal_high = np.array(goal_high)

        self.reward_type = reward_type
        self.norm_order = norm_order
        self.indicator_threshold = indicator_threshold

        self.fix_goal = fix_goal
        self.fixed_goal = np.array(fixed_goal)
        self._state_goal = None

        self.hide_goal_markers = hide_goal_markers

        self.action_space = Box(np.array([-1, -1, -1]), np.array([1, 1, 1]))
        self.hand_and_puck_space = Box(
            np.hstack((self.hand_low, puck_low)),
            np.hstack((self.hand_high, puck_high)),
        )
        self.hand_space = Box(self.hand_low, self.hand_high)
        self.observation_space = Dict([
            ('observation', self.hand_and_puck_space),
            ('desired_goal', self.hand_and_puck_space),
            ('achieved_goal', self.hand_and_puck_space),
            ('state_observation', self.hand_and_puck_space),
            ('state_desired_goal', self.hand_and_puck_space),
            ('state_achieved_goal', self.hand_and_puck_space),
            ('proprio_observation', self.hand_space),
            ('proprio_desired_goal', self.hand_space),
            ('proprio_achieved_goal', self.hand_space),
        ])
        self.init_puck_z = init_puck_z
        self.reset_free = reset_free
        self._set_puck_xy(self.sample_puck_xy())
        self.reset_counter = 0
        self.num_resets_before_puck_reset = num_resets_before_puck_reset

    @property
    def model_name(self):
        return get_asset_full_path('sawyer_xyz/sawyer_push_puck.xml')

    def viewer_setup(self):
        self.viewer.cam.trackbodyid = 0
        self.viewer.cam.lookat[0] = 0
        self.viewer.cam.lookat[1] = 1.0
        self.viewer.cam.lookat[2] = 0.5
        self.viewer.cam.distance = 0.3
        self.viewer.cam.elevation = -45
        self.viewer.cam.azimuth = 270
        self.viewer.cam.trackbodyid = -1

    def step(self, action):
        self.set_xyz_action(action)
        self.do_simulation(np.array([1]))
        self._set_goal_marker(self._state_goal)
        ob = self._get_obs()
        reward = self.compute_reward(action, ob)
        info = self._get_info()
        done = False
        return ob, reward, done, info

    def _get_obs(self):
        e = self.get_endeff_pos()
        b = self.get_puck_pos()[:2]
        flat_obs = np.concatenate((e, b))

        return dict(
            observation=flat_obs,
            desired_goal=self._state_goal,
            achieved_goal=flat_obs,
            state_observation=flat_obs,
            state_desired_goal=self._state_goal,
            state_achieved_goal=flat_obs,
            proprio_observation=flat_obs[:3],
            proprio_desired_goal=self._state_goal[:3],
            proprio_achieved_goal=flat_obs[:3],
        )

    def _get_info(self):
        hand_goal = self._state_goal[:3]
        puck_goal = self._state_goal[3:]

        # hand distance
        hand_diff = hand_goal - self.get_endeff_pos()
        hand_distance = np.linalg.norm(hand_diff, ord=self.norm_order)
        hand_distance_l1 = np.linalg.norm(hand_diff, 1)
        hand_distance_l2 = np.linalg.norm(hand_diff, 2)

        # puck distance
        puck_diff = puck_goal - self.get_puck_pos()[:2]
        puck_distance = np.linalg.norm(puck_diff, ord=self.norm_order)
        puck_distance_l1 = np.linalg.norm(puck_diff, 1)
        puck_distance_l2 = np.linalg.norm(puck_diff, 2)

        # touch distance
        touch_diff = self.get_endeff_pos() - self.get_puck_pos()
        touch_distance = np.linalg.norm(touch_diff, ord=self.norm_order)
        touch_distance_l1 = np.linalg.norm(touch_diff, ord=1)
        touch_distance_l2 = np.linalg.norm(touch_diff, ord=2)

        # state distance
        state_diff = np.hstack((self.get_endeff_pos(), self.get_puck_pos()[:2])) - self._state_goal
        state_distance = np.linalg.norm(state_diff, ord=self.norm_order)
        state_distance_l1 = np.linalg.norm(state_diff, ord=1)
        state_distance_l2 = np.linalg.norm(state_diff, ord=2)

        return dict(
            hand_distance=hand_distance,
            hand_distance_l1=hand_distance_l1,
            hand_distance_l2=hand_distance_l2,
            puck_distance=puck_distance,
            puck_distance_l1=puck_distance_l1,
            puck_distance_l2=puck_distance_l2,
            hand_and_puck_distance=hand_distance+puck_distance,
            hand_and_puck_distance_l1=hand_distance_l1+puck_distance_l1,
            hand_and_puck_distance_l2=hand_distance_l2+puck_distance_l2,
            touch_distance=touch_distance,
            touch_distance_l1=touch_distance_l1,
            touch_distance_l2=touch_distance_l2,
            state_distance=state_distance,
            state_distance_l1=state_distance_l1,
            state_distance_l2=state_distance_l2,
            hand_success=float(hand_distance < self.indicator_threshold),
            puck_success=float(puck_distance < self.indicator_threshold),
            hand_and_puck_success=float(
                hand_distance+puck_distance < self.indicator_threshold
            ),
            touch_success=float(touch_distance < self.indicator_threshold),
            state_success=float(state_distance < self.indicator_threshold),
        )

    def get_puck_pos(self):
        return self.data.get_body_xpos('puck').copy()

    def sample_puck_xy(self):
        return np.array([0, 0.6])

    def _set_goal_marker(self, goal):
        """
        This should be use ONLY for visualization. Use self._state_goal for
        logging, learning, etc.
        """
        self.data.site_xpos[self.model.site_name2id('hand-goal-site')] = (
            goal[:3]
        )
        self.data.site_xpos[self.model.site_name2id('puck-goal-site')][:2] = (
            goal[3:]
        )
        if self.hide_goal_markers:
            self.data.site_xpos[self.model.site_name2id('hand-goal-site'), 2] = (
                -1000
            )
            self.data.site_xpos[self.model.site_name2id('puck-goal-site'), 2] = (
                -1000
            )

    def _set_puck_xy(self, pos):
        qpos = self.data.qpos.flat.copy()
        qvel = self.data.qvel.flat.copy()
        qpos[7:10] = np.hstack((pos.copy(), np.array([self.init_puck_z])))
        qpos[10:14] = np.array([1, 0, 0, 0])
        qvel[7:14] = 0
        self.set_state(qpos, qvel)

    def reset_model(self):
        self._reset_hand()
        goal = self.sample_goal()
        self.set_goal(goal)
        if self.reset_free:
            if self.reset_counter % self.num_resets_before_puck_reset == 0:
                self._set_puck_xy(self.sample_puck_xy())
            elif not Box(self.puck_low, self.puck_high).contains(self.get_puck_pos()[:2]):
                self._set_puck_xy(self.sample_puck_xy())
        else:
            self._set_puck_xy(self.sample_puck_xy())
        self.reset_counter += 1
        self.reset_mocap_welds()
        return self._get_obs()

    def _reset_hand(self):
        velocities = self.data.qvel.copy()
        angles = self.data.qpos.copy()
        angles[:7] = self.init_angles[:7]
        self.set_state(angles.flatten(), velocities.flatten())
        for _ in range(10):
            self.data.set_mocap_pos('mocap', np.array([0, 0.4, 0.02]))
            self.data.set_mocap_quat('mocap', np.array([1, 0, 1, 0]))
        sim = self.sim
        if sim.model.nmocap > 0 and sim.model.eq_data is not None:
            for i in range(sim.model.eq_data.shape[0]):
                if sim.model.eq_type[i] == mujoco_py.const.EQ_WELD:
                    # Define the xyz + quat of the mocap relative to the hand
                    sim.model.eq_data[i, :] = np.array(
                        [0., 0., 0., 1., 0., 0., 0.]
                    )

    def reset(self):
        ob = self.reset_model()
        if self.viewer is not None:
            self.viewer_setup()
        return ob

    @property
    def init_angles(self):
        return [1.78026069e+00, - 6.84415781e-01, - 1.54549231e-01,
                2.30672090e+00, 1.93111471e+00,  1.27854012e-01,
                1.49353907e+00,
                1.80196716e-03, 7.40415706e-01, 2.09895360e-02,
                1, 0, 0, 0
                ]

    """
    Multitask functions
    """
    def get_goal(self):
        return {
            'desired_goal': self._state_goal,
            'state_desired_goal': self._state_goal,
        }

    def set_goal(self, goal):
        self._state_goal = goal['state_desired_goal']
        self._set_goal_marker(self._state_goal)

    def set_to_goal(self, goal):
        hand_goal = goal['state_desired_goal'][:3]
        for _ in range(10):
            self.data.set_mocap_pos('mocap', hand_goal)
            self.data.set_mocap_quat('mocap', np.array([1, 0, 1, 0]))
            self.do_simulation(None, self.frame_skip)
        puck_goal = goal['state_desired_goal'][3:]
        self._set_puck_xy(puck_goal)
        self.sim.forward()

    def sample_goals(self, batch_size):
        if self.fix_goal:
            goals = np.repeat(
                self.fixed_goal.copy()[None],
                batch_size,
                0
            )
        else:
            goals = np.random.uniform(
                self.goal_low,
                self.goal_high,
                size=(batch_size, self.goal_low.size),
            )
        return {
            'desired_goal': goals,
            'state_desired_goal': goals,
        }

    def compute_rewards(self, actions, obs):
        achieved_goals = obs['state_achieved_goal']
        desired_goals = obs['state_desired_goal']
        hand_pos = achieved_goals[:, :3]
        puck_pos = achieved_goals[:, 3:]
        hand_goals = desired_goals[:, :3]
        puck_goals = desired_goals[:, 3:]

        hand_distances = np.linalg.norm(hand_goals - hand_pos, ord=self.norm_order, axis=1)
        puck_distances = np.linalg.norm(puck_goals - puck_pos, ord=self.norm_order, axis=1)
        puck_zs = self.init_puck_z * np.ones((desired_goals.shape[0], 1))
        touch_distances = np.linalg.norm(
            hand_pos - np.hstack((puck_pos, puck_zs)),
            ord=self.norm_order,
            axis=1,
        )

        if self.reward_type == 'hand_distance':
            r = -hand_distances
        elif self.reward_type == 'hand_success':
            r = -(hand_distances < self.indicator_threshold).astype(float)
        elif self.reward_type == 'puck_distance':
            r = -puck_distances
        elif self.reward_type == 'puck_success':
            r = -(puck_distances < self.indicator_threshold).astype(float)
        elif self.reward_type == 'state_distance':
            r = -np.linalg.norm(
                achieved_goals - desired_goals,
                ord=self.norm_order,
                axis=1
            )
        elif self.reward_type == 'vectorized_state_distance':
            r = -np.abs(achieved_goals - desired_goals)
        elif self.reward_type == 'touch_distance':
            r = -touch_distances
        elif self.reward_type == 'touch_success':
            r = -(touch_distances < self.indicator_threshold).astype(float)
        else:
            raise NotImplementedError("Invalid/no reward type.")
        return r

    def get_diagnostics(self, paths, prefix=''):
        statistics = OrderedDict()
        for stat_name in [
            'hand_distance',
            'hand_distance_l1',
            'hand_distance_l2',
            'puck_distance',
            'puck_distance_l1',
            'puck_distance_l2',
            'hand_and_puck_distance',
            'hand_and_puck_distance_l1',
            'hand_and_puck_distance_l2',
            'state_distance',
            'state_distance_l1',
            'state_distance_l2',
            'touch_distance',
            'touch_distance_l1',
            'touch_distance_l2',
            'hand_success',
            'puck_success',
            'hand_and_puck_success',
            'state_success',
            'touch_success',
        ]:
            stat_name = stat_name
            stat = get_stat_in_paths(paths, 'env_infos', stat_name)
            statistics.update(create_stats_ordered_dict(
                '%s%s' % (prefix, stat_name),
                stat,
                always_show_all_stats=True,
                ))
            statistics.update(create_stats_ordered_dict(
                'Final %s%s' % (prefix, stat_name),
                [s[-1] for s in stat],
                always_show_all_stats=True,
                ))
        return statistics

    def get_env_state(self):
        base_state = super().get_env_state()
        goal = self._state_goal.copy()
        return base_state, goal

    def set_env_state(self, state):
        base_state, goal = state
        super().set_env_state(base_state)
        self._state_goal = goal
        self._set_goal_marker(goal)


class SawyerPushAndReachXYEnv(SawyerPushAndReachXYZEnv):
    def __init__(self, *args, hand_z_position=0.02, **kwargs):
        self.quick_init(locals())
        SawyerPushAndReachXYZEnv.__init__(self, *args, **kwargs)
        self.hand_z_position = hand_z_position
        self.action_space = Box(np.array([-1, -1]), np.array([1, 1]))
        self.fixed_goal[2] = hand_z_position
        hand_and_puck_low = self.hand_and_puck_space.low.copy()
        hand_and_puck_low[2] = hand_z_position
        hand_and_puck_high = self.hand_and_puck_space.high.copy()
        hand_and_puck_high[2] = hand_z_position
        self.hand_and_puck_space = Box(hand_and_puck_low, hand_and_puck_high)
        self.observation_space = Dict([
            ('observation', self.hand_and_puck_space),
            ('desired_goal', self.hand_and_puck_space),
            ('achieved_goal', self.hand_and_puck_space),
            ('state_observation', self.hand_and_puck_space),
            ('state_desired_goal', self.hand_and_puck_space),
            ('state_achieved_goal', self.hand_and_puck_space),
            ('proprio_observation', self.hand_space),
            ('proprio_desired_goal', self.hand_space),
            ('proprio_achieved_goal', self.hand_space),
        ])

    def step(self, action):
        delta_z = self.hand_z_position - self.data.mocap_pos[0, 2]
        action = np.hstack((action, delta_z))
        return super().step(action)
