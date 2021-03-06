import gym # openai gym
# from unrealcv_cmd import  UnrealCv # a lib for using unrealcv client command
from gym_unrealcv.envs.utils.unrealcv_basic import UnrealCv
from gym import spaces
import numpy as np
import math
import os
from gym_unrealcv.envs.utils import env_unreal
from gym_unrealcv.envs.navigation.interaction import Navigation
import random
from math import sin, cos, radians

from gym_unrealcv.envs.utils.utils_depthFusion import write_pose, write_depth, depth_fusion, depth_conversion, poseRelToAbs, poseOrigin, depth_fusion_mult
import time
# import pcl
import open3d as o3d
o3d.set_verbosity_level(o3d.VerbosityLevel.Error)
# import run_docker # a lib for run env in a docker container
# import gym_unrealcv.envs.utils.run_docker

import tensorflow as tf
from tensorflow.python.framework import ops
import keras.backend as K



class depthFusion_keras_multHouse(gym.Env):
    # init the Unreal Gym Environment
    def __init__(self,
                setting_file = 'depth_fusion.json',
                reset_type = 'waypoint',       # testpoint, waypoint,
                augment_env = None,   #texture, target, light
                test = True,               # if True will use the test_xy as start point
                action_type = 'discrete',  # 'discrete', 'continuous'
                observation_type = 'rgbd', # 'color', 'depth', 'rgbd'
                reward_type = 'bbox', # distance, bbox, bbox_distance,
                docker = False,
                # resolution = (84,84)
                # resolution = (640,480),
                resolution = (640,480),
                log_dir='log/'
    ):
     setting = self.load_env_setting(setting_file)
     self.cam_id = 0
     # self.reset_type = 'random'
     self.reset_type = 'test'
     self.log_dir = log_dir
     # gt_pcl = pcl.load('house-000024-gt.ply')

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

     self.observation_type = observation_type
     assert self.observation_type == 'color' or self.observation_type == 'depth' or self.observation_type == 'rgbd' or self.observation_type == 'gray'
     self.observation_shape = self.unrealcv.define_observation(self.cam_id,self.observation_type)

     self.startpose = self.unrealcv.get_pose(self.cam_id)

     #try hardcode start pose
     # self.startpose = [750.0, 295.0, 212.3,356.5,190.273, 0.0]
     # self.startpose = [0.0, 707.1068, 707.1067,0.0,270.0, -45.0] # [0,45,1000]
     # self.startpose = [0.0,99.6,8.72,0.0,270.0,-5.0] #[for depth fusion] [0,5,100]
     # self.startpose = [0.0,70.7,70.7,0.0,270.0,-45.0]
     azimuth, elevation, distance = self.start_pose_rel
     # print('start pose rel', azimuth,elevation,distance)
     self.startpose = poseRelToAbs(azimuth, elevation, distance)
     # print('start_pose: ', self.startpose)
     ''' create base frame '''
     poseOrigin(self.log_dir+'frame-{:06}.pose.txt'.format(1000))
     # ACTION: (Azimuth, Elevation, Distance)

     self.count_steps = 0
     self.count_house_frames = 0
     # self.max_steps = 35
     self.target_pos = ( -60,   0,   50)
     self.gt_pclpose_prev = np.array(self.start_pose_rel)
     # self.action_space = gym.spaces.Discrete(len(self.ACTION_LIST))
     # state = self.unrealcv.read_image(self.cam_id, 'lit')
     # self.observation_space = gym.spaces.Box(low=0, high=255, shape=state.shape)

     self.nn_distance_module =tf.load_op_library('/home/daryl/gym-unrealcv/gym_unrealcv/envs/utils/tf_nndistance_so.so')
     self.total_distance = 0

     objects = self.unrealcv.get_objects()
     # print('objects', objects)
     self.houses = [(obj) for obj in objects if obj.startswith('BAT6_')]
     # print('houses', self.houses)
     for house in self.houses:
         self.unrealcv.hide_obj(house)

     self.house_id = 0
     self.unrealcv.show_obj(self.houses[self.house_id])

     gt_dir = '/hdd/AIRSCAN/datasets/house38_44/groundtruth/'

     self.gt_pcl = []
     for i in range(len(self.houses)):
         gt_fn = gt_dir + self.houses[i] + '_sampled_10k.ply'
         # print('gt', gt_fn)
         # gt_pcl = pcl.load(gt_fn)
         gt_pcl = o3d.read_point_cloud(gt_fn)
         gt_pcl = np.asarray(gt_pcl.points, dtype=np.float32)
         # gt_pcl = pcl.load('/home/daryl/datasets/BAT6_SETA_HOUSE8_WTR_sampled_10k.ply')
         # gt_pcl = np.asarray(gt_pcl)
         self.gt_pcl.append(np.expand_dims(gt_pcl,axis=0))

    def _step(self, action = 0):
        # (velocity, angle) = self.ACTION_LIST[action]
        self.count_steps += 1
        self.count_house_frames +=1
        azimuth, elevation, distance  = self.discrete_actions[action]
        change_pose = np.array((azimuth, elevation, distance))

        pose_prev = np.array(self.pose_prev)
        # print('pose prev', pose_prev)
        # print('action', change_pose)

        MIN_elevation = 20
        MAX_elevation = 70
        MIN_distance = 100
        # MAX_distance = 150
        MAX_distance = 125

        pose_new = pose_prev + change_pose
        # pose_new = pose_prev + np.array([30,0,0]) # to test ICM
        if pose_new[2] > MAX_distance:
            pose_new[2] = MAX_distance
        elif pose_new[2] < MIN_distance:
            pose_new[2] = MIN_distance
        if (pose_new[1] >= MAX_elevation):
            pose_new[1] = MAX_elevation
        elif (pose_new[1] <= MIN_elevation):
            pose_new[1] = MIN_elevation
        else:
            pose_new[1] = 45.0
        if (pose_new[0] < 0):
            pose_new[0] = 360 + pose_new[0]
        elif (pose_new[0]>=359):
            pose_new[0] = pose_new[0] - 360

        # print('action ', action)
        # print('pose new', pose_new)
        # print(azimuth, elevation, distance )
        # collision, move_dist = self.unrealcv.move_rel2(self.cam_id, azimuth, elevation, distance)
        collision, move_dist = self.unrealcv.move_rel2(self.cam_id, pose_new[0], pose_new[1], pose_new[2])
        # print('collision', collision)
        # print('distance:   ', move_dist)

        self.pose_prev =pose_new
        # state = self.unrealcv.read_image(self.cam_id, 'lit')
        state = self.unrealcv.get_observation(self.cam_id, self.observation_type)
        # print('state shape', state.shape)
        depth_pt = self.unrealcv.read_depth(self.cam_id,mode='depthFusion')
        pose = self.unrealcv.get_pose(self.cam_id,'soft')
        depth = depth_conversion(depth_pt, 320)
        # pose_filename = self.log_dir+'frame-{:06}.pose.txt'.format(self.count_steps)
        # depth_filename = self.log_dir+'frame-{:06}.depth.npy'.format(self.count_steps)
        pose_filename = self.log_dir+'frame-{:06}.pose-{:06}.txt'.format(self.count_house_frames, self.house_id)
        depth_filename = self.log_dir+'frame-{:06}.depth-{:06}.npy'.format(self.count_house_frames, self.house_id)
        write_pose(pose, pose_filename)
        np.save(depth_filename, depth)
        reward, done = self.reward(collision,move_dist)


        # limit max step per episode
        if self.count_steps > self.max_steps:
            done = True
            # print('Reach Max Steps')

        return state, reward, done, {}

    # reset the environment
    def _reset(self, start_pose_rel = None):

       x,y,z,_, yaw, _ = self.startpose
       self.house_id = 0

       for house in self.houses:
           self.unrealcv.hide_obj(house)

       self.unrealcv.show_obj(self.houses[self.house_id])

       if self.reset_type == 'random':
           distance = 1000
           azimuth = 0
           elevation = 45

           p=90
           distance = distance + random.randint(-250,250)
           azimuth = random.randint(0,359)
           elevation = random.randint(35,55)

           yaw_exp = 270 - azimuth
           pitch = -1*elevation

           y = distance*sin(radians(p-elevation))*cos(radians(azimuth))
           x = distance*sin(radians(p-elevation))*sin(radians(azimuth))

           z = distance*cos(radians(p-elevation))

           self.unrealcv.set_pose(self.cam_id,[x,y,z,0,yaw_exp,pitch]) # pose = [x, y, z, roll, yaw, pitch]

       else:
           self.unrealcv.set_pose(self.cam_id,self.startpose) # pose = [x, y, z, roll, yaw, pitch]

       state = self.unrealcv.get_observation(self.cam_id, self.observation_type)

       self.count_steps = 0
       self.count_house_frames = 0

       depth_pt = self.unrealcv.read_depth(self.cam_id,mode='depthFusion')
       pose = self.unrealcv.get_pose(self.cam_id,'soft')
       depth = depth_conversion(depth_pt, 320)
       # depth_filename = self.log_dir+'frame-{:06}.depth-{:06}.npy'.format(self.count_steps)
       # pose_filename = self.log_dir+'frame-{:06}.pose-{:06}.txt'.format(self.count_steps)
       pose_filename = self.log_dir+'frame-{:06}.pose-{:06}.txt'.format(self.count_house_frames, self.house_id)
       depth_filename = self.log_dir+'frame-{:06}.depth-{:06}.npy'.format(self.count_house_frames, self.house_id)
       write_pose(pose, pose_filename)
       np.save(depth_filename, depth)

       out_pcl_np = depth_fusion_mult(self.log_dir, first_frame_idx =0, base_frame_idx=1000, num_frames = self.count_house_frames + 1, save_pcd = False, max_depth = 1.0, house_id=self.house_id)
       # out_fn = 'log/house-' + '{:06}'.format(self.count_steps+1) + '.ply'
       # out_pcl = pcl.load(out_fn)
       # out_pcl_np = np.asarray(out_pcl)
       out_pcl_np = np.expand_dims(out_pcl_np,axis=0)
       self.cd_old = self.compute_chamfer(out_pcl_np)
       # print('cd old ', self.cd_old)
       self.pose_prev = np.array(self.start_pose_rel)

       return  state

    # close docker while closing openai gym
    # def _close(self):
       # self.docker.close()

    # calcuate reward according to your task
    def reward(self,collision, move_dist):

       done = False

       depth_start = time.time()

       out_pcl_np = depth_fusion_mult(self.log_dir, first_frame_idx =0, base_frame_idx=1000, num_frames = self.count_house_frames + 1, save_pcd = False, max_depth = 1.0, house_id=self.house_id)
       # print('out_pcl_np', out_pcl_np.shape)
       if out_pcl_np.shape[0] != 0:
           out_pcl_np = np.expand_dims(out_pcl_np,axis=0)
           cd = self.compute_chamfer(out_pcl_np)
       else:
           cd = 0.0
       cd_delta = cd - self.cd_old

       depth_end = time.time()


       # print("Depth Fusion time: ", depth_end - depth_start)
       # print('coverage: ', cd)
       if cd > 96.0:

           self.unrealcv.hide_obj(self.houses[self.house_id])
           self.house_id += 1

           if (self.house_id == len(self.houses)):
               done = True
               # reward = 50
               reward = 50
           else:
                # print('covered', self.count_steps)
               # print('new house')
               self.unrealcv.show_obj(self.houses[self.house_id])
               self.count_house_frames = 0
               reward = 100

               self.unrealcv.set_pose(self.cam_id,self.startpose)
               depth_pt = self.unrealcv.read_depth(self.cam_id,mode='depthFusion')
               pose = self.unrealcv.get_pose(self.cam_id,'soft')
               depth = depth_conversion(depth_pt, 320)
               # depth_filename = self.log_dir+'frame-{:06}.depth-{:06}.npy'.format(self.count_steps)
               # pose_filename = self.log_dir+'frame-{:06}.pose-{:06}.txt'.format(self.count_steps)
               pose_filename = self.log_dir+'frame-{:06}.pose-{:06}.txt'.format(self.count_house_frames, self.house_id)
               depth_filename = self.log_dir+'frame-{:06}.depth-{:06}.npy'.format(self.count_house_frames, self.house_id)
               write_pose(pose, pose_filename)
               np.save(depth_filename, depth)

               out_pcl_np = depth_fusion_mult(self.log_dir, first_frame_idx =0, base_frame_idx=1000, num_frames = self.count_house_frames + 1, save_pcd = False, max_depth = 1.0, house_id=self.house_id)
               # out_fn = 'log/house-' + '{:06}'.format(self.count_steps+1) + '.ply'
               # out_pcl = pcl.load(out_fn)
               # out_pcl_np = np.asarray(out_pcl)
               out_pcl_np = np.expand_dims(out_pcl_np,axis=0)
               self.cd_old = self.compute_chamfer(out_pcl_np)
               self.pose_prev = np.array(self.start_pose_rel)

       else:
           # reward = cd_delta*0.2
           reward = cd_delta
           # reward = cd_delta*0.4
           reward += -2 # added to push minimization of steps

       self.cd_old = cd
       self.total_distance += move_dist

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
       self.start_pose_rel = setting['start_pose_rel']
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

    def compute_chamfer(self, output):
       # with tf.Session('') as sess:
       # sess = K.get_session()
       # self.sess.run(tf.global_variables_initializer())
       # loss_out = self.sess.run(loss,feed_dict={inp_placeholder: output})
       with tf.device('/gpu:0'):
           sess = K.get_session()
           with sess.as_default():
           # with tf.Session('') as sess:

               # inp_placeholder = tf.placeholder(tf.float32)
               # reta,retb,retc,retd=self.nn_distance(inp_placeholder,self.gt_pcl)
               # with tf.name_scope('chamfer'):
               # reta,retb,retc,retd=self.nn_distance(output,self.gt_pcl)
               _,_,retc,_=self.nn_distance(output,self.gt_pcl[self.house_id])
               # loss=tf.reduce_sum(reta)+tf.reduce_sum(retc)

               # loss=tf.reduce_sum(retc)
               dist_thresh = tf.greater(0.0008, retc)
               dist_mean = tf.reduce_mean(tf.cast(dist_thresh, tf.float32))

               # loss_out = tf.Tensor.eval(loss)
               coverage = tf.Tensor.eval(dist_mean)
               # coverage2 = tf.Tensor.eval(dist_mean2)
               # print('coverage2 ', coverage2)
               # loss_out = self.sess.run(loss,feed_dict={inp_placeholder: output})
               # print('coverage ', coverage)
               return coverage*100

    def nn_distance(self,xyz1,xyz2):
       '''
     Computes the distance of nearest neighbors for a pair of point clouds
     input: xyz1: (batch_size,#points_1,3)  the first point cloud
     input: xyz2: (batch_size,#points_2,3)  the second point cloud
     output: dist1: (batch_size,#point_1)   distance from first to second
     output: idx1:  (batch_size,#point_1)   nearest neighbor from first to second
     output: dist2: (batch_size,#point_2)   distance from second to first
     output: idx2:  (batch_size,#point_2)   nearest neighbor from second to first
       '''
       return self.nn_distance_module.nn_distance(xyz1,xyz2)
