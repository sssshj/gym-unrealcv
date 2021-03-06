import gym # openai gym
# from unrealcv_cmd import  UnrealCv # a lib for using unrealcv client command
from gym_unrealcv.envs.utils.unrealcv_basic import UnrealCv
from gym import spaces
import numpy as np
import math
import os
from gym_unrealcv.envs.utils import env_unreal
from gym_unrealcv.envs.navigation.interaction import Navigation
from gym_unrealcv.envs.navigation import reward
import cv2
# import run_docker # a lib for run env in a docker container
# import gym_unrealcv.envs.utils.run_docker

class sfmHouseTarget(gym.Env):
    # init the Unreal Gym Environment
    def __init__(self,
                setting_file = 'sfmHouseTarget.json',
                reset_type = 'waypoint',       # testpoint, waypoint,
                augment_env = None,   #texture, target, light
                test = True,               # if True will use the test_xy as start point
                action_type = 'discrete',  # 'discrete', 'continuous'
                observation_type = 'rgbd', # 'color', 'depth', 'rgbd'
                reward_type = 'bbox', # distance, bbox, bbox_distance,
                docker = False,
                # resolution = (320,240)
                resolution = (640,480)
    ):
     setting = self.load_env_setting(setting_file)
     self.cam_id = 0

     # run virtual enrionment in docker container
     # self.docker = run_docker.RunDocker()
     # env_ip, env_dir = self.docker.start(ENV_NAME=ENV_NAME)

     # start unreal env
     docker = False
     # self.unreal = env_unreal.RunUnreal(ENV_BIN="house_withfloor/MyProject2/Binaries/Linux/MyProject2")
     self.unreal = env_unreal.RunUnreal(ENV_BIN=self.env_bin)
     env_ip,env_port = self.unreal.start(docker,resolution)

     # connect unrealcv client to server
     # self.unrealcv = UnrealCv(self.cam_id, ip=env_ip, env=env_dir)


     # connect UnrealCV
     self.unrealcv = Navigation(cam_id=self.cam_id,
                              port= env_port,
                              ip=env_ip,
                              targets=self.target_list,
                              env=self.unreal.path2env,
                              resolution=resolution)
     self.unrealcv.pitch = self.pitch

      # define action
     self.action_type = action_type
     assert self.action_type == 'discrete' or self.action_type == 'continuous'
     if self.action_type == 'discrete':
         self.action_space = spaces.Discrete(len(self.discrete_actions))
     elif self.action_type == 'continuous':
         self.action_space = spaces.Box(low = np.array(self.continous_actions['low']),high = np.array(self.continous_actions['high']))

     self.startpose = self.unrealcv.get_pose(self.cam_id)
     print('start_pose: ', self.startpose)
     #try hardcode start pose
     # self.startpose = [750.0, 295.0, 212.3,356.5,190.273, 0.0]
     self.startpose = [0.0, 707.1068, 707.1067,0.0,270.0, -45.0] # [0,45,1000]
     # ACTION: (Azimuth, Elevation, Distance)
     print("start")
     object_mask = self.unrealcv.read_image(self.cam_id, 'object_mask', mode='file')
     cv2.imshow('object_mask', object_mask)
     cv2.waitKey(0)
     boxes = self.unrealcv.get_bboxes(object_mask, self.target_list)

     # ACTION: (linear velocity ,angle velocity)
     # self.ACTION_LIST = [
     #         (20,  0),
     #         (20, 15),
     #         (20,-15),
     #         (20, 30),
     #         (20,-30),
     # ]
     self.count_steps = 0
     # self.max_steps = 35
     self.target_pos = ( -60,   0,   50)
     # self.action_space = gym.spaces.Discrete(len(self.ACTION_LIST))
     state = self.unrealcv.read_image(self.cam_id, 'lit')
     self.observation_space = gym.spaces.Box(low=0, high=255, shape=state.shape)

     self.reward_type = reward_type
     self.reward_function = reward.Reward(setting)


    # update the environment step by step
    def _step(self, action = 0):
        # (velocity, angle) = self.ACTION_LIST[action]
        self.count_steps += 1
        # collision =  self.unrealcv.move(self.cam_id, angle, velocity)
        # collision = self.unrealcv.move_2d(self.cam_id, angle, velocity)
        # collision = self.unrealcv.move_2d(self.cam_id, angle, velocity)
        azimuth, elevation, distance = action
        collision, move_dist = self.unrealcv.move_rel(self.cam_id, azimuth, elevation, distance)

        # print('distance:   ', move_dist)
        print('reward type: ', self.reward_type)
        print('target list: ', self.target_list)
        if 'bbox' in self.reward_type:
            object_mask = self.unrealcv.read_image(self.cam_id, 'object_mask')
            cv2.imshow('object_mask', object_mask)
            cv2.waitKey(0)
            boxes = self.unrealcv.get_bboxes(object_mask, self.target_list)
            reward_bbox, bbox = self.reward_function.reward_bbox(boxes)
            print('bbox reward: ', reward_bbox, bbox)
        reward, done = self.reward(collision,move_dist)
        state = self.unrealcv.read_image(self.cam_id, 'lit')

        # limit max step per episode
        if self.count_steps > self.max_steps:
            done = True
            print('Reach Max Steps')

        return state, reward, done, {}

    # reset the environment
    def _reset(self, ):
       x,y,z,_, yaw, _ = self.startpose
       pose = self.startpose

       # self.unrealcv.set_position(self.cam_id, x, y, z)
       # self.unrealcv.set_rotation(self.cam_id, 0, yaw, 0)

       self.unrealcv.set_pose(self.cam_id,self.startpose)

       state = self.unrealcv.read_image(self.cam_id, 'lit')
       self.count_steps = 0
       return  state

    # close docker while closing openai gym
    # def _close(self):
       # self.docker.close()

    # calcuate reward according to your task
    def reward(self,collision, move_dist):
       done = False
       reward = - 0.01

       if collision:
            done = True
            reward = -1
            print('Collision Detected!!')
       else:
            #hard code to 1
            reward = -1*move_dist*(1/2000)
            # print('dist reward: ', reward)
            # distance = self.cauculate_distance(self.target_pos, self.unrealcv.get_pose())
            # if distance < 50:
            #     reward = 10
            #     done = True
            #     print ('Get Target Place!')
       return reward, done

    # calcuate the 2D distance between the target and camera
    def cauculate_distance(self,target,current):
       error = abs(np.array(target) - np.array(current))[:2]# only x and y
       distance = math.sqrt(sum(error * error))
       return distance

    def load_env_setting(self,filename):
       f = open(self.get_settingpath(filename))
       type = os.path.splitext(filename)[1]
       if type == '.json':
            import json
            setting = json.load(f)
       elif type == '.yaml':
            import yaml
            setting = yaml.load(f)
       else:
            print('unknown type')

       self.cam_id = setting['cam_id']
       self.target_list = setting['targets']
       self.max_steps = setting['maxsteps']
       self.trigger_th = setting['trigger_th']
       self.height = setting['height']
       self.pitch = setting['pitch']

       self.discrete_actions = setting['discrete_actions']
       self.continous_actions = setting['continous_actions']
       self.env_bin = setting['env_bin']
       self.env_name = setting['env_name']
       print('env name: ', self.env_name)
       print('env id: ', setting['env_bin'])
       return setting

    def get_settingpath(self, filename):
       import gym_unrealcv
       gympath = os.path.dirname(gym_unrealcv.__file__)
       return os.path.join(gympath, 'envs/setting', filename)
