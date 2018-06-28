from collections import OrderedDict
import numpy as np
from gym.spaces import Box, Dict

from multiworld.envs.env_util import get_stat_in_paths, \
    create_stats_ordered_dict, get_asset_full_path
from multiworld.core.multitask_env import MultitaskEnv
from multiworld.envs.mujoco.sawyer_xyz.base import SawyerXYZEnv
from multiworld.envs.mujoco.cameras import sawyer_pick_and_place_camera


class SawyerPickAndPlaceEnv(MultitaskEnv, SawyerXYZEnv):
    def __init__(
            self,
            obj_low=None,
            obj_high=None,

            reward_type='hand_and_obj_distance',
            indicator_threshold=0.06,

            obj_init_pos=(0, 0.6, 0.03),

            fix_goal=False,
            fixed_goal=(0.15, 0.6, 0.055, -0.15, 0.6),
            goal_low=None,
            goal_high=None,

            hide_goal_markers=False,
            hide_arm=False,

            **kwargs
    ):
        self.quick_init(locals())
        MultitaskEnv.__init__(self)
        self.hide_arm = hide_arm
        SawyerXYZEnv.__init__(
            self,
            model_name=self.model_name,
            **kwargs
        )
        if obj_low is None:
            obj_low = self.hand_low
        if obj_high is None:
            obj_high = self.hand_high

        if goal_low is None:
            goal_low = np.hstack((self.hand_low, obj_low))
        if goal_high is None:
            goal_high = np.hstack((self.hand_high, obj_high))

        self.reward_type = reward_type
        self.indicator_threshold = indicator_threshold

        self.obj_init_pos = np.array(obj_init_pos)

        self.fix_goal = fix_goal
        self.fixed_goal = np.array(fixed_goal)
        self._state_goal = None

        self.hide_goal_markers = hide_goal_markers

        self.action_space = Box(
            np.array([-1, -1, -1, -1]),
            np.array([1, 1, 1, 1]),
        )
        self.hand_and_obj_space = Box(
            np.hstack((self.hand_low, obj_low)),
            np.hstack((self.hand_high, obj_high)),
        )
        self.observation_space = Dict([
            ('observation', self.hand_and_obj_space),
            ('desired_goal', self.hand_and_obj_space),
            ('achieved_goal', self.hand_and_obj_space),
            ('state_observation', self.hand_and_obj_space),
            ('state_desired_goal', self.hand_and_obj_space),
            ('state_achieved_goal', self.hand_and_obj_space),
        ])

    @property
    def model_name(self):
        if self.hide_arm:
            print('hiding')
            return get_asset_full_path('sawyer_xyz/sawyer_pick_and_place_hidden_arm.xml')
        print('not hiding')
        return get_asset_full_path('sawyer_xyz/sawyer_pick_and_place.xml')

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
        self.set_xyz_action(action[:3])
        self.do_simulation(action[3:])
        # The marker seems to get reset every time you do a simulation
        self._set_goal_marker(self._state_goal)
        ob = self._get_obs()
        reward = self.compute_reward(action, ob)
        info = self._get_info()
        done = False
        return ob, reward, done, info

    def _get_obs(self):
        e = self.get_endeff_pos()
        b = self.get_obj_pos()
        flat_obs = np.concatenate((e, b))

        return dict(
            observation=flat_obs,
            desired_goal=self._state_goal,
            achieved_goal=flat_obs,
            state_observation=flat_obs,
            state_desired_goal=self._state_goal,
            state_achieved_goal=flat_obs,
        )

    def _get_info(self):
        hand_goal = self._state_goal[:3]
        obj_goal = self._state_goal[3:]
        hand_distance = np.linalg.norm(hand_goal - self.get_endeff_pos())
        obj_distance = np.linalg.norm(obj_goal - self.get_obj_pos())
        touch_distance = np.linalg.norm(
            self.get_endeff_pos() - self.get_obj_pos()
        )
        return dict(
            hand_distance=hand_distance,
            obj_distance=obj_distance,
            hand_and_obj_distance=hand_distance+obj_distance,
            touch_distance=touch_distance,
            hand_success=float(hand_distance < self.indicator_threshold),
            obj_success=float(obj_distance < self.indicator_threshold),
            hand_and_obj_success=float(
                hand_distance+obj_distance < self.indicator_threshold
            ),
            touch_success=float(touch_distance < self.indicator_threshold),
        )

    def get_obj_pos(self):
        return self.data.get_body_xpos('obj').copy()

    def _set_goal_marker(self, goal):
        """
        This should be use ONLY for visualization. Use self._state_goal for
        logging, learning, etc.
        """
        self.data.site_xpos[self.model.site_name2id('hand-goal-site')] = (
            goal[:3]
        )
        self.data.site_xpos[self.model.site_name2id('obj-goal-site')] = (
            goal[3:]
        )
        if self.hide_goal_markers:
            self.data.site_xpos[self.model.site_name2id('hand-goal-site'), 2] = (
                -1000
            )
            self.data.site_xpos[self.model.site_name2id('obj-goal-site'), 2] = (
                -1000
            )

    def _set_obj_xyz(self, pos):
        qpos = self.data.qpos.flat.copy()
        qvel = self.data.qvel.flat.copy()
        qpos[8:11] = pos.copy()
        qvel[8:15] = 0
        self.set_state(qpos, qvel)

    def reset_model(self):
        self._reset_hand()
        goal = self.sample_goal()
        self._state_goal = goal['state_desired_goal']
        self._set_goal_marker(self._state_goal)

        self._set_obj_xyz(self.obj_init_pos)
        return self._get_obs()

    def _reset_hand(self):
        for _ in range(10):
            self.data.set_mocap_pos('mocap', np.array([0, 0.5, 0.02]))
            self.data.set_mocap_quat('mocap', np.array([1, 0, 1, 0]))
            self.do_simulation(None, self.frame_skip)

    def put_obj_in_hand(self):
        new_obj_pos = self.data.get_site_xpos('endeffector')
        new_obj_pos[1] -= 0.02
        new_obj_pos[2] += 0.03
        self.do_simulation(-1)
        self._set_obj_xyz(new_obj_pos)
        self.do_simulation(1)

    def set_to_goal(self, goal):
        state_goal = goal['state_desired_goal']
        hand_goal = state_goal[:3]
        for _ in range(30):
            self.data.set_mocap_pos('mocap', hand_goal)
            self.data.set_mocap_quat('mocap', np.array([1, 0, 1, 0]))
            # keep gripper closed
            self.do_simulation(np.array([-1]))
        error = self.data.get_site_xpos('endeffector') - hand_goal
        self._set_obj_xyz(state_goal[3:] + error)
        self.do_simulation(np.array([1]))
        self.sim.forward()

    """
    Multitask functions
    """
    def get_goal(self):
        return {
            'desired_goal': self._state_goal,
            'state_desired_goal': self._state_goal,
        }

    def sample_goals(self, batch_size, p_obj_in_hand=.75):
        if self.fix_goal:
            goals = np.repeat(
                self.fixed_goal.copy()[None],
                batch_size,
                0
            )
        else:
            goals = np.random.uniform(
                self.hand_and_obj_space.low,
                self.hand_and_obj_space.high,
                size=(batch_size, self.hand_and_obj_space.low.size),
            )
        num_objs_in_hand = int(batch_size * p_obj_in_hand)
        if batch_size == 1:
            num_objs_in_hand = int(np.random.random() < p_obj_in_hand)
        # Put object in hand
        goals[:num_objs_in_hand, 3:] = goals[:num_objs_in_hand, :3].copy()
        goals[:num_objs_in_hand, 4] -= 0.02
        goals[:num_objs_in_hand, 5] += 0.02

        # Put object one the table (not floating)
        goals[num_objs_in_hand:, 5] = self.obj_init_pos[2]
        return {
            'desired_goal': goals,
            'state_desired_goal': goals,
        }

    def compute_rewards(self, actions, obs):
        achieved_goals = obs['state_achieved_goal']
        desired_goals = obs['state_desired_goal']
        hand_pos = achieved_goals[:, :3]
        obj_pos = achieved_goals[:, 3:]
        hand_goals = desired_goals[:, :3]
        obj_goals = desired_goals[:, 3:]

        hand_distances = np.linalg.norm(hand_goals - hand_pos, axis=1)
        obj_distances = np.linalg.norm(obj_goals - obj_pos, axis=1)
        hand_and_obj_distances = hand_distances + obj_distances
        touch_distances = np.linalg.norm(hand_pos - obj_pos, axis=1)

        if self.reward_type == 'hand_distance':
            r = -hand_distances
        elif self.reward_type == 'hand_success':
            r = -(hand_distances < self.indicator_threshold).astype(float)
        elif self.reward_type == 'obj_distance':
            r = -obj_distances
        elif self.reward_type == 'obj_success':
            r = -(obj_distances < self.indicator_threshold).astype(float)
        elif self.reward_type == 'hand_and_obj_distance':
            r = -hand_and_obj_distances
        elif self.reward_type == 'hand_and_obj_success':
            r = -(
                hand_and_obj_distances < self.indicator_threshold
            ).astype(float)
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
            'obj_distance',
            'hand_and_obj_distance',
            'touch_distance',
            'hand_success',
            'obj_success',
            'hand_and_obj_success',
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

class SawyerPickAndPlaceEnvYZ(SawyerPickAndPlaceEnv):

    def __init__(
        self,
        x_axis=0.0,
        oracle_resets=False,
        *args,
        **kwargs
    ):
        self.quick_init(locals())
        super().__init__(*args, **kwargs)
        self.oracle_resets = oracle_resets
        self.x_axis = x_axis
        pos_arrays = [
            self.hand_and_obj_space.low[:3],
            self.hand_and_obj_space.low[3:],
            self.hand_and_obj_space.high[:3],
            self.hand_and_obj_space.high[3:],
        ]
        for pos in pos_arrays:
            pos[0] = x_axis

        self.observation_space = Dict([
            ('observation', self.hand_and_obj_space),
            ('desired_goal', self.hand_and_obj_space),
            ('achieved_goal', self.hand_and_obj_space),
            ('state_observation', self.hand_and_obj_space),
            ('state_desired_goal', self.hand_and_obj_space),
            ('state_achieved_goal', self.hand_and_obj_space),
        ])
        self.action_space = Box(
            np.array([-1, -1, -1]),
            np.array([1, 1, 1]),
        )

    def reset_model(self):
        self._reset_hand()
        goal = self.sample_goal()
        self._state_goal = goal['state_desired_goal']
        self._set_goal_marker(self._state_goal)

        self._set_obj_xyz(self.obj_init_pos)
        if self.oracle_resets:
            self.set_to_goal(self.sample_goal())
        return self._get_obs()

    def viewer_setup(self):
        sawyer_pick_and_place_camera(self.viewer.cam)

    def convert_2d_action(self, action):
        cur_x_pos = self.get_endeff_pos()[0]
        adjust_x = self.x_axis - cur_x_pos
        return np.r_[adjust_x, action]

    def step(self, action):
        # new_obj_pos = self.data.get_site_xpos('obj')
        # new_obj_pos[0] = self.x_axis
        # self._set_obj_xyz(new_obj_pos)

        action = self.convert_2d_action(action)
        return super().step(action)

    def _reset_hand(self):
        for _ in range(10):
            self.data.set_mocap_pos('mocap', np.array([0, 0.6, 0.2]))
            self.data.set_mocap_quat('mocap', np.array([1, 0, 1, 0]))
            self.do_simulation(None, self.frame_skip)

    def _move_hand(self, hand_pos, gripper_action):
        for _ in range(30):
            self.data.set_mocap_pos('mocap', hand_pos)
            self.data.set_mocap_quat('mocap', np.array([1, 0, 1, 0]))
            # keep gripper closed
            self.do_simulation(np.array([gripper_action]))

    def sample_hand_pos(self, batch_size):
        goals = np.random.uniform(
            self.hand_and_obj_space.low,
            self.hand_and_obj_space.high,
            size=(batch_size, self.hand_and_obj_space.low.size),
        )
        return goals[:, :3]

    def move_to_random_pos_with_block(self):
        hand_pos = self.sample_hand_pos(1)[0]
        self._move_hand(hand_pos, -1)
        self.put_obj_in_hand()

    def set_to_goal(self, goal):
        state_goal = goal['state_desired_goal']
        hand_goal = state_goal[:3]
        for _ in range(30):
            self.data.set_mocap_pos('mocap', hand_goal)
            self.data.set_mocap_quat('mocap', np.array([1, 0, 1, 0]))
            self.do_simulation(np.array([-1]))
        error = self.data.get_site_xpos('endeffector') - hand_goal
        corrected_obj_pos = state_goal[3:] + error
        corrected_obj_pos[0] = self.x_axis
        corrected_obj_pos[2] = max(corrected_obj_pos[2], self.obj_init_pos[2])
        self._set_obj_xyz(corrected_obj_pos)
        action = np.array(1 - 2 * (np.random.random() > .8))
        if state_goal[5] == self.obj_init_pos[2]:
            action = np.array(1 - 2 * (np.random.random() > .5))
        self.do_simulation(action)
        new_obj_pos = self.data.get_site_xpos('obj')
#        new_obj_pos[0] = self.x_axis
#        self._set_obj_xyz(new_obj_pos)
        self.sim.forward()


