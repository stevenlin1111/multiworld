from collections import OrderedDict
import logging

import numpy as np
from gym import spaces
from pygame import Color

from multiworld.core.multitask_env import MultitaskEnv
from multiworld.core.serializable import Serializable
from multiworld.envs.env_util import (
    get_stat_in_paths,
    create_stats_ordered_dict,
)
from multiworld.envs.pygame.pygame_viewer import PygameViewer
from multiworld.envs.pygame.walls import VerticalWall, HorizontalWall


class Point2DEnv(MultitaskEnv, Serializable):
    """
    A little 2D point whose life goal is to reach a target.
    """

    def __init__(
            self,
            render_dt_msec=0,
            action_l2norm_penalty=0,  # disabled for now
            render_onscreen=False,
            render_size=84,
            reward_type="dense",
            action_scale=1.0,
            target_radius=0.60,
            boundary_dist=4,
            ball_radius=0.50,
            walls=None,
            fixed_goal=None,
            randomize_position_on_reset=True,
            fixed_reset=None,
            images_are_rgb=False,  # else black and white
            show_goal=True,
            expl_goal_sampler=None,
            eval_goal_sampler=None,
            use_fixed_reset_for_eval=False,
            **kwargs
    ):
        if walls is None:
            walls = []
        if walls is None:
            walls = []
        if fixed_goal is not None:
            fixed_goal = np.array(fixed_goal)
        if len(kwargs) > 0:
            LOGGER = logging.getLogger(__name__)
            LOGGER.log(logging.WARNING, "WARNING, ignoring kwargs:", kwargs)
        self.quick_init(locals())
        self.render_dt_msec = render_dt_msec
        self.action_l2norm_penalty = action_l2norm_penalty
        self.render_onscreen = render_onscreen
        self.render_size = render_size
        self.reward_type = reward_type
        self.action_scale = action_scale
        self.target_radius = target_radius
        self.boundary_dist = boundary_dist
        self.ball_radius = ball_radius
        self.walls = walls
        self.fixed_goal = fixed_goal
        self.randomize_position_on_reset = randomize_position_on_reset
        self.images_are_rgb = images_are_rgb
        self.show_goal = show_goal

        self.max_target_distance = self.boundary_dist - self.target_radius

        self._target_position = None
        self._position = np.zeros((2))

        u = np.ones(2)
        self.action_space = spaces.Box(-u, u, dtype=np.float32)

        o = self.boundary_dist * np.ones(2)
        self.obs_range = spaces.Box(-o, o, dtype='float32')
        self.observation_space = spaces.Dict([
            ('observation', self.obs_range),
            ('desired_goal', self.obs_range),
            ('achieved_goal', self.obs_range),
            ('state_observation', self.obs_range),
            ('state_desired_goal', self.obs_range),
            ('state_achieved_goal', self.obs_range),
        ])

        self.drawer = None
        self.render_drawer = None
        self.goal_sampling_mode = "test"
        self.fixed_reset = fixed_reset
        self.expl_goal_sampler = expl_goal_sampler
        self.eval_goal_sampler = eval_goal_sampler

        self.presampled_goals = None
        self.use_fixed_reset_for_eval = use_fixed_reset_for_eval

    def step(self, velocities):
        assert self.action_scale <= 1.0
        velocities = np.clip(velocities, a_min=-1, a_max=1) * self.action_scale
        new_position = self._position + velocities
        orig_new_pos = new_position.copy()
        for wall in self.walls:
            new_position = wall.handle_collision(
                self._position, new_position
            )
        if sum(new_position != orig_new_pos) > 1:
            """
            Hack: sometimes you get caught on two walls at a time. If you
            process the input in the other direction, you might only get
            caught on one wall instead.
            """
            new_position = orig_new_pos.copy()
            for wall in self.walls[::-1]:
                new_position = wall.handle_collision(
                    self._position, new_position
                )

        self._position = new_position
        self._position = np.clip(
            self._position,
            a_min=-self.boundary_dist,
            a_max=self.boundary_dist,
        )
        distance_to_target = np.linalg.norm(
            self._position - self._target_position
        )
        is_success = distance_to_target < self.target_radius

        ob = self._get_obs()
        reward = self.compute_reward(velocities, ob)
        info = {
            'radius': self.target_radius,
            'target_position': self._target_position,
            'distance_to_target': distance_to_target,
            'velocity': velocities,
            'speed': np.linalg.norm(velocities),
            'is_success': is_success,
        }
        done = False
        return ob, reward, done, info


    def reset(self):
        self._target_position = self.sample_goal()['state_desired_goal']
        if self.goal_sampling_mode == 'test' and self.use_fixed_reset_for_eval:
            self._position = self.fixed_reset
        elif self.randomize_position_on_reset:
            self._position = self._sample_position(
                self.obs_range.low,
                self.obs_range.high,
            )
        elif self.fixed_reset is not None:
            self._position = self.fixed_reset
        return self._get_obs()

    def _position_inside_wall(self, pos):
        for wall in self.walls:
            if wall.contains_point(pos):
                return True
        return False

    def _sample_position(self, low, high):
        pos = np.random.uniform(low, high)
        while self._position_inside_wall(pos) is True:
            pos = np.random.uniform(low, high)
        return pos

    def _get_obs(self):
        return dict(
            observation=self._position.copy(),
            desired_goal=self._target_position.copy(),
            achieved_goal=self._position.copy(),
            state_observation=self._position.copy(),
            state_desired_goal=self._target_position.copy(),
            state_achieved_goal=self._position.copy(),
        )

    def compute_rewards(self, actions, obs):
        achieved_goals = obs['state_achieved_goal']
        desired_goals = obs['state_desired_goal']
        d = np.linalg.norm(achieved_goals - desired_goals, axis=-1)
        if self.reward_type == "sparse":
            return -(d > self.target_radius).astype(np.float32)
        elif self.reward_type == "dense":
            return -d
        elif self.reward_type == "dense_l1":
            return -np.linalg.norm(achieved_goals - desired_goals, axis=-1,
                                   ord=1)
        elif self.reward_type == 'vectorized_dense':
            return -np.abs(achieved_goals - desired_goals)
        else:
            raise NotImplementedError()

    def get_diagnostics(self, paths, prefix=''):
        statistics = OrderedDict()
        for stat_name in [
            'radius',
            'target_position',
            'distance_to_target',
            'velocity',
            'speed',
            'is_success',
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

    def get_goal(self):
        return {
            'desired_goal': self._target_position.copy(),
            'state_desired_goal': self._target_position.copy(),
        }

    def set_goal(self, goal):
        self._target_position = goal['state_desired_goal']

    def sample_goals(self, batch_size):
        if self.goal_sampling_mode == 'train' and self.expl_goal_sampler:
            return self.expl_goal_sampler(self, batch_size)
        if self.goal_sampling_mode == 'test' and self.eval_goal_sampler:
            return self.eval_goal_sampler(self, batch_size)
        assert self.goal_sampling_mode is None, "Invalid goal sampling mode: {}".format(self.goal_sampling_mode)

        if not self.fixed_goal is None:
            goals = np.repeat(
                self.fixed_goal.copy()[None],
                batch_size,
                0
            )
        else:
            if self.presampled_goals is None:
                goals = np.zeros((10000, self.obs_range.low.size))
                for b in range(10000):
                    goals[b, :] = self._sample_position(
                        self.obs_range.low,
                        self.obs_range.high,
                    )
                self.presampled_goals = {
                    'desired_goal': goals,
                    'state_desired_goal': goals,
                }
        random_idxs = np.random.choice(len(list(self.presampled_goals.values())[0]), size=batch_size)
        return {
            'desired_goal': self.presampled_goals['desired_goal'][random_idxs],
            'state_desired_goal': self.presampled_goals['state_desired_goal'][random_idxs],
        }

    def get_image_plt(self, vals, vmin=None, vmax=None, extent=[-4, 4, -4, 4],
                      small_markers=False, draw_walls=True, draw_state=True,
                      draw_goal=True, draw_subgoals=False, imsize=None):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.set_ylim(extent[2:4])
        ax.set_xlim(extent[0:2])
        ax.set_ylim(ax.get_ylim()[::-1])
        DPI = fig.get_dpi()
        if imsize is None:
            fig.set_size_inches(self.render_size / float(DPI), self.render_size / float(DPI))
        else:
            fig.set_size_inches(imsize / float(DPI), imsize / float(DPI))

        marker_factor = 0.60
        if small_markers:
            marker_factor = 0.10
        if draw_walls:
            for wall in self.walls:
                ax.vlines(x=wall.endpoint1[0], ymin=wall.endpoint2[1], ymax=wall.endpoint1[1])
                ax.hlines(y=wall.endpoint2[1], xmin=wall.endpoint3[0], xmax=wall.endpoint2[0])
                ax.vlines(x=wall.endpoint3[0], ymin=wall.endpoint3[1], ymax=wall.endpoint4[1])
                ax.hlines(y=wall.endpoint4[1], xmin=wall.endpoint4[0], xmax=wall.endpoint1[0])
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)
        fig.subplots_adjust(bottom=0)
        fig.subplots_adjust(top=1)
        fig.subplots_adjust(right=1)
        fig.subplots_adjust(left=0)
        ax.axis('off')

        ax.imshow(
            vals,
            extent=extent,
            cmap=plt.get_cmap('plasma'),
            interpolation='nearest',
            vmax=vmax,
            vmin=vmin,
            origin='bottom',  # <-- Important! By default top left is (0, 0)
        )
        fig.canvas.draw()
        data = np.fromstring(fig.canvas.tostring_rgb(), dtype=np.uint8, sep='')
        data = data.reshape(fig.canvas.get_width_height()[::-1] + (3,))
        plt.close()
        # X and Y are flipped for some reason
        data = data.transpose((1, 0, 2))
        # Not sure why this is needed for Image envs
        if hasattr(self, 'transpose') and self.transpose:
            data = data[:, ::-1, :]
        # Normal processing from the image env
        data = data.transpose(2, 1, 0).flatten()
        return data

    def get_mesh_grid(self, observation_key, granularity=.4):
        vals = np.arange(-self.boundary_dist, self.boundary_dist, granularity)
        grid = np.zeros((len(vals), len(vals), 2))
        for i in range(len(vals)):
            for j in range(len(vals)):
                grid[i, j] =np.array([vals[i], vals[j]])
        grid = grid.reshape(-1, 2)
        return grid

    def set_position(self, pos):
        self._position[0] = pos[0]
        self._position[1] = pos[1]

    """Functions for ImageEnv wrapper"""

    def get_image(self, width=None, height=None):
        """Returns a black and white image"""
        if self.drawer is None:
            if width != height:
                raise NotImplementedError()
            self.drawer = PygameViewer(
                screen_width=width,
                screen_height=height,
                x_bounds=(-self.boundary_dist - self.ball_radius, self.boundary_dist + self.ball_radius),
                y_bounds=(-self.boundary_dist - self.ball_radius, self.boundary_dist + self.ball_radius),
                render_onscreen=self.render_onscreen,
            )
        self.draw(self.drawer)
        img = self.drawer.get_image()
        if self.images_are_rgb:
            return img.transpose((1, 0, 2))
        else:
            r, g, b = img[:, :, 0], img[:, :, 1], img[:, :, 2]
            img = (-r + b).transpose().flatten()
            return img

    def set_to_goal(self, goal_dict):
        goal = goal_dict["state_desired_goal"]
        self._position = goal
        self._target_position = goal

    def get_env_state(self):
        return self._get_obs()

    def set_env_state(self, state):
        position = state["state_observation"]
        goal = state["state_desired_goal"]
        self._position = position
        self._target_position = goal

    def draw(self, drawer):
        drawer.fill(Color('white'))
        if self.show_goal:
            drawer.draw_solid_circle(
                self._target_position,
                self.target_radius,
                Color('green'),
            )
        drawer.draw_solid_circle(
            self._position,
            self.ball_radius,
            Color('blue'),
        )

        for wall in self.walls:
            drawer.draw_segment(
                wall.endpoint1,
                wall.endpoint2,
                Color('black'),
            )
            drawer.draw_segment(
                wall.endpoint2,
                wall.endpoint3,
                Color('black'),
            )
            drawer.draw_segment(
                wall.endpoint3,
                wall.endpoint4,
                Color('black'),
            )
            drawer.draw_segment(
                wall.endpoint4,
                wall.endpoint1,
                Color('black'),
            )
        drawer.render()

    def render(self, mode='human', close=False):
        if close:
            self.render_drawer = None
            return

        if self.render_drawer is None or self.render_drawer.terminated:
            self.render_drawer = PygameViewer(
                self.render_size,
                self.render_size,
                x_bounds=(-self.boundary_dist-self.ball_radius, self.boundary_dist+self.ball_radius),
                y_bounds=(-self.boundary_dist-self.ball_radius, self.boundary_dist+self.ball_radius),
                render_onscreen=True,
            )
        self.draw(self.render_drawer)
        self.render_drawer.tick(self.render_dt_msec)
        if mode != 'interactive':
            self.render_drawer.check_for_exit()

    def get_diagnostics(self, paths, prefix=''):
        statistics = OrderedDict()
        for stat_name in [
            'distance_to_target',
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

    """Static visualization/utility methods"""

    @staticmethod
    def true_model(state, action):
        velocities = np.clip(action, a_min=-1, a_max=1)
        position = state
        new_position = position + velocities
        return np.clip(
            new_position,
            a_min=-Point2DEnv.boundary_dist,
            a_max=Point2DEnv.boundary_dist,
        )

    @staticmethod
    def true_states(state, actions):
        real_states = [state]
        for action in actions:
            next_state = Point2DEnv.true_model(state, action)
            real_states.append(next_state)
            state = next_state
        return real_states

    @staticmethod
    def plot_trajectory(ax, states, actions, goal=None):
        assert len(states) == len(actions) + 1
        x = states[:, 0]
        y = -states[:, 1]
        num_states = len(states)
        plasma_cm = plt.get_cmap('plasma')
        for i, state in enumerate(states):
            color = plasma_cm(float(i) / num_states)
            ax.plot(state[0], -state[1],
                    marker='o', color=color, markersize=10,
                    )

        actions_x = actions[:, 0]
        actions_y = -actions[:, 1]

        ax.quiver(x[:-1], y[:-1], x[1:] - x[:-1], y[1:] - y[:-1],
                  scale_units='xy', angles='xy', scale=1, width=0.005)
        ax.quiver(x[:-1], y[:-1], actions_x, actions_y, scale_units='xy',
                  angles='xy', scale=1, color='r',
                  width=0.0035, )
        ax.plot(
            [
                -Point2DEnv.boundary_dist,
                -Point2DEnv.boundary_dist,
            ],
            [
                Point2DEnv.boundary_dist,
                -Point2DEnv.boundary_dist,
            ],
            color='k', linestyle='-',
        )
        ax.plot(
            [
                Point2DEnv.boundary_dist,
                -Point2DEnv.boundary_dist,
            ],
            [
                Point2DEnv.boundary_dist,
                Point2DEnv.boundary_dist,
            ],
            color='k', linestyle='-',
        )
        ax.plot(
            [
                Point2DEnv.boundary_dist,
                Point2DEnv.boundary_dist,
            ],
            [
                Point2DEnv.boundary_dist,
                -Point2DEnv.boundary_dist,
            ],
            color='k', linestyle='-',
        )
        ax.plot(
            [
                Point2DEnv.boundary_dist,
                -Point2DEnv.boundary_dist,
            ],
            [
                -Point2DEnv.boundary_dist,
                -Point2DEnv.boundary_dist,
            ],
            color='k', linestyle='-',
        )

        if goal is not None:
            ax.plot(goal[0], -goal[1], marker='*', color='g', markersize=15)
        ax.set_ylim(
            -Point2DEnv.boundary_dist - 1,
            Point2DEnv.boundary_dist + 1,
        )
        ax.set_xlim(
            -Point2DEnv.boundary_dist - 1,
            Point2DEnv.boundary_dist + 1,
        )

    def initialize_camera(self, init_fctn):
        pass


class Point2DWallEnv(Point2DEnv):
    """Point2D with walls"""

    def __init__(
            self,
            wall_shape="",
            wall_thickness=1.0,
            inner_wall_max_dist=1,
            **kwargs
    ):
        self.quick_init(locals())
        super().__init__(**kwargs)
        self.inner_wall_max_dist = inner_wall_max_dist
        self.wall_shape = wall_shape
        self.wall_thickness = wall_thickness
        if wall_shape == "u":
            self.walls = [
                # Right wall
                VerticalWall(
                    self.ball_radius,
                    self.inner_wall_max_dist,
                    -self.inner_wall_max_dist,
                    self.inner_wall_max_dist,
                ),
                # Left wall
                VerticalWall(
                    self.ball_radius,
                    -self.inner_wall_max_dist,
                    -self.inner_wall_max_dist,
                    self.inner_wall_max_dist,
                ),
                # Bottom wall
                HorizontalWall(
                    self.ball_radius,
                    self.inner_wall_max_dist,
                    -self.inner_wall_max_dist,
                    self.inner_wall_max_dist,
                )
            ]
        if wall_shape == "-" or wall_shape == "h":
            self.walls = [
                HorizontalWall(
                    self.ball_radius,
                    self.inner_wall_max_dist,
                    -self.inner_wall_max_dist,
                    self.inner_wall_max_dist,
                )
            ]
        if wall_shape == "--":
            self.walls = [
                HorizontalWall(
                    self.ball_radius,
                    0,
                    -self.inner_wall_max_dist,
                    self.inner_wall_max_dist,
                )
            ]
        if wall_shape == "-|":
            self.walls = [
                HorizontalWall(
                    self.ball_radius,
                    1.5 * self.inner_wall_max_dist,
                    0.5 * self.inner_wall_max_dist,
                    1.5 * self.inner_wall_max_dist,
                    self.wall_thickness
                ),
                VerticalWall(
                    self.ball_radius,
                    1.5 * self.inner_wall_max_dist,
                    0.5 * self.inner_wall_max_dist,
                    1.5 * self.inner_wall_max_dist,
                    self.wall_thickness
                )
            ]
        if wall_shape == "4-|":
            min_val = 1.25
            max_val = 2.25
            self.max_val = max_val
            self.min_val = min_val
            self.walls = [
                HorizontalWall(
                    self.ball_radius,
                    max_val * self.inner_wall_max_dist,
                    min_val * self.inner_wall_max_dist,
                    max_val * self.inner_wall_max_dist,
                    self.wall_thickness
                ),
                VerticalWall(
                    self.ball_radius,
                    max_val * self.inner_wall_max_dist,
                    min_val * self.inner_wall_max_dist,
                    max_val * self.inner_wall_max_dist,
                    self.wall_thickness
                ),
                HorizontalWall(
                    self.ball_radius,
                    max_val * self.inner_wall_max_dist,
                    -max_val * self.inner_wall_max_dist,
                    -min_val * self.inner_wall_max_dist,
                    self.wall_thickness,
                ),
                VerticalWall(
                    self.ball_radius,
                    -max_val * self.inner_wall_max_dist,
                    min_val * self.inner_wall_max_dist,
                    max_val * self.inner_wall_max_dist,
                    self.wall_thickness
                ),

                HorizontalWall(
                    self.ball_radius,
                    -max_val * self.inner_wall_max_dist,
                    -max_val * self.inner_wall_max_dist,
                    -min_val * self.inner_wall_max_dist,
                    self.wall_thickness,
                ),
                VerticalWall(
                    self.ball_radius,
                    -max_val * self.inner_wall_max_dist,
                    -max_val * self.inner_wall_max_dist,
                    -min_val * self.inner_wall_max_dist,
                    self.wall_thickness
                ),


                HorizontalWall(
                    self.ball_radius,
                    -max_val * self.inner_wall_max_dist,
                    min_val * self.inner_wall_max_dist,
                    max_val * self.inner_wall_max_dist,
                    self.wall_thickness,
                ),
                VerticalWall(
                    self.ball_radius,
                    max_val * self.inner_wall_max_dist,
                    -max_val * self.inner_wall_max_dist,
                    -min_val * self.inner_wall_max_dist,
                    self.wall_thickness
                ),
            ]

        if wall_shape == "big-u":
            self.walls = [
                VerticalWall(
                    self.ball_radius,
                    self.inner_wall_max_dist*2,
                    -self.inner_wall_max_dist*2,
                    self.inner_wall_max_dist,
                    self.wall_thickness
                ),
                # Left wall
                VerticalWall(
                    self.ball_radius,
                    -self.inner_wall_max_dist*2,
                    -self.inner_wall_max_dist*2,
                    self.inner_wall_max_dist,
                    self.wall_thickness
                ),
                # Bottom wall
                HorizontalWall(
                    self.ball_radius,
                    self.inner_wall_max_dist,
                    -self.inner_wall_max_dist*2,
                    self.inner_wall_max_dist*2,
                    self.wall_thickness
                ),
            ]
        if wall_shape == "easy-u":
            self.walls = [
                VerticalWall(
                    self.ball_radius,
                    self.inner_wall_max_dist*2,
                    -self.inner_wall_max_dist*0.5,
                    self.inner_wall_max_dist,
                    self.wall_thickness
                ),
                # Left wall
                VerticalWall(
                    self.ball_radius,
                    -self.inner_wall_max_dist*2,
                    -self.inner_wall_max_dist*0.5,
                    self.inner_wall_max_dist,
                    self.wall_thickness
                ),
                # Bottom wall
                HorizontalWall(
                    self.ball_radius,
                    self.inner_wall_max_dist,
                    -self.inner_wall_max_dist*2,
                    self.inner_wall_max_dist*2,
                    self.wall_thickness
                ),
            ]
        if wall_shape == "big-h":
            self.walls = [
                # Bottom wall
                HorizontalWall(
                    self.ball_radius,
                    self.inner_wall_max_dist,
                    -self.inner_wall_max_dist*2,
                    self.inner_wall_max_dist*2,
                ),
            ]
        if wall_shape == "box":
            self.walls = [
                # Bottom wall
                VerticalWall(
                    self.ball_radius,
                    0,
                    0,
                    0,
                    self.wall_thickness
                ),
            ]
        if wall_shape == "none":
            self.walls = []


if __name__ == "__main__":
    import gym
    import matplotlib.pyplot as plt

    # e = gym.make('Point2D-Box-Wall-v1')
    # e = gym.make('Point2D-Big-UWall-v1')
    e = gym.make('Point2D-Easy-UWall-v1')
    for i in range(1000):
        e.reset()
        for j in range(5):
            e.step(np.random.rand(2))
            e.render()
            im = e.get_image()
