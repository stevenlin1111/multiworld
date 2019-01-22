import numpy as np

def create_sawyer_camera_init(
        lookat=(0, 0.85, 0.3),
        distance=0.3,
        elevation=-35,
        azimuth=270,
        trackbodyid=-1,
):
    def init(camera):
        camera.lookat[0] = lookat[0]
        camera.lookat[1] = lookat[1]
        camera.lookat[2] = lookat[2]
        camera.distance = distance
        camera.elevation = elevation
        camera.azimuth = azimuth
        camera.trackbodyid = trackbodyid

    return init


def init_sawyer_camera_v1(camera):
    """
    Do not get so close that the arm crossed the camera plane
    """
    camera.lookat[0] = 0
    camera.lookat[1] = 1
    camera.lookat[2] = 0.3
    camera.distance = 0.35
    camera.elevation = -35
    camera.azimuth = 270
    camera.trackbodyid = -1


def init_sawyer_camera_v2(camera):
    """
    Top down basically. Sees through the arm.
    """
    camera.lookat[0] = 0
    camera.lookat[1] = 0.8
    camera.lookat[2] = 0.3
    camera.distance = 0.3
    camera.elevation = -65
    camera.azimuth = 270
    camera.trackbodyid = -1


def init_sawyer_camera_v3(camera):
    """
    Top down basically. Sees through the arm.
    """
    camera.lookat[0] = 0
    camera.lookat[1] = 0.85
    camera.lookat[2] = 0.3
    camera.distance = 0.3
    camera.elevation = -35
    camera.azimuth = 270
    camera.trackbodyid = -1


def init_sawyer_camera_v4(camera):
    """
    This is the same camera used in old experiments (circa 6/7/2018)
    """
    camera.lookat[0] = 0
    camera.lookat[1] = 0.85
    camera.lookat[2] = 0.3
    camera.distance = 0.3
    camera.elevation = -35
    camera.azimuth = 270
    camera.trackbodyid = -1

def init_sawyer_camera_v5(camera):
    """
    Purposely zoomed out to be hard.
    """
    camera.lookat[0] = 0
    camera.lookat[1] = 0.85
    camera.lookat[2] = 0.3
    camera.distance = 1
    camera.elevation = -35
    camera.azimuth = 270
    camera.trackbodyid = -1


def sawyer_pick_and_place_camera(camera):
    camera.lookat[0] = 0.0
    camera.lookat[1] = .67
    camera.lookat[2] = .1
    camera.distance = .7
    camera.elevation = 0
    camera.azimuth = 180
    camera.trackbodyid = 0


def sawyer_pick_and_place_camera_slanted_angle(camera):
    camera.lookat[0] = 0.0
    camera.lookat[1] = .67
    camera.lookat[2] = .1
    camera.distance = .65
    camera.elevation = -37.85
    camera.azimuth = 180
    camera.trackbodyid = 0


def sawyer_xyz_reacher_camera_v0(camera):
    camera.lookat[0] = 0
    camera.lookat[1] = 0.85
    camera.lookat[2] = 0.3
    camera.distance = 0.4
    camera.elevation = -35
    camera.azimuth = 270
    camera.trackbodyid = -1


def sawyer_torque_reacher_camera(camera):
    camera.distance = .3
    camera.lookat[0] = 0
    camera.lookat[1] = 1.0
    camera.lookat[2] = 0.65
    camera.elevation = -30
    camera.azimuth = 270
    camera.trackbodyid = -1


def sawyer_door_env_camera_v0(camera):
    camera.distance = 0.25
    camera.lookat[0] = -.2
    camera.lookat[1] = 0.55
    camera.lookat[2] = 0.6
    camera.elevation = -60
    camera.azimuth = 360
    camera.trackbodyid = -1


def sawyer_pusher_camera_upright_v0(camera):
    camera.distance = .2
    camera.lookat[0] = 0
    camera.lookat[1] = 0.85
    camera.lookat[2] = 0.45
    camera.elevation = -50
    camera.azimuth = 270
    camera.trackbodyid = -1


def sawyer_pusher_camera_upright_v2(camera):
    camera.distance = .45
    camera.lookat[0] = 0
    camera.lookat[1] = 0.85
    camera.lookat[2] = 0.45
    camera.elevation = -60
    camera.azimuth = 270
    camera.trackbodyid = -1


def sawyer_pusher_camera_upright_v3(camera):
    camera.distance = .275
    camera.lookat[0] = 0
    camera.lookat[1] = 0.85
    camera.lookat[2] = 0.45
    camera.elevation = -65
    camera.azimuth = 270
    camera.trackbodyid = -1


def sawyer_pusher_camera_top_down(camera):
    camera.trackbodyid = 0
    cam_dist = 0.1
    rotation_angle = 0
    cam_pos = np.array([0, 0.6, .9, cam_dist, -90, rotation_angle])

    for i in range(3):
        camera.lookat[i] = cam_pos[i]
    camera.distance = cam_pos[3]
    camera.elevation = cam_pos[4]
    camera.azimuth = cam_pos[5]
    camera.trackbodyid = -1

def sawyer_door_side_camera(camera):
    # -0.199165796861 0.579504471951 0.331416868819 1.141999569051058 -19.74293059125965 -0.6940874035989693
    camera.lookat[0] = -.2
    camera.lookat[1] = .58
    camera.lookat[2] = .33
    camera.distance = 1.14
    camera.elevation = -19.74

def sawyer_door_angled_camera(camera):
    #-0.318599359444 0.611850100287 0.230596331934 0.5985720207596054 -22.056555269922885 58.071979434447336
    camera.lookat[0] = -.32
    camera.lookat[1] = .61
    camera.lookat[2] = .23
    camera.distance = .6
    camera.elevation = -12


def sawyer_init_camera_zoomed_in(camera):
    camera.trackbodyid = 0
    camera.distance = 1.0

    # robot view
    #rotation_angle = 90
    #cam_dist = 1
    #cam_pos = np.array([0, 0.5, 0.2, cam_dist, -45, rotation_angle])

    # 3rd person view
    cam_dist = 0.3
    rotation_angle = 270
    cam_pos = np.array([0, 0.85, 0.2, cam_dist, -45, rotation_angle])

    # top down view
    #cam_dist = 0.2
    #rotation_angle = 0
    #cam_pos = np.array([0, 0, 1.5, cam_dist, -90, rotation_angle])

    for i in range(3):
        camera.lookat[i] = cam_pos[i]
    camera.distance = cam_pos[3]
    camera.elevation = cam_pos[4]
    camera.azimuth = cam_pos[5]
    camera.trackbodyid = -1

