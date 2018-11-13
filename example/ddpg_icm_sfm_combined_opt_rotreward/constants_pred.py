# ENV_NAME = 'house-plain-v1'
ENV_NAME = 'curiosityChangePos-v0'

CONTINUE = True
RESTART_EP = 300

TRAIN = False
SHOW = True
MAP = False


TF_DEVICE = '/gpu:0'
MAX_EPOCHS = 10000
MAX_EPOCHS = RESTART_EP+1
MAX_STEPS_PER_EPOCH = 10000
MEMORY_SIZE = 50000
LEARN_START_STEP = 10000
MAX_EXPLORE_STEPS = 20000

INPUT_SIZE = 84 # pre 100
BATCH_SIZE = 32
LEARNINGRATE_CRITIC  = 0.001
LEARNINGRATE_ACTOR = 0.0001
TARGET_UPDATE_RATE = 0.001
LEARNINGRATE_ICM = 0.001

GAMMA = 0.95
INITIAL_EPSILON = 1  # starting value of epsilon
FINAL_EPSILON = 0.1  # final value of epsilon


TEST_INTERVAL_EPOCHS = 1000
SAVE_INTERVAL_EPOCHS = 500

LOG_NAME_SAVE = 'log'
MONITOR_DIR = LOG_NAME_SAVE + '/monitor/' #the path to save monitor file
MODEL_DIR = LOG_NAME_SAVE + '/model' # the path to save deep model
PARAM_DIR = LOG_NAME_SAVE + '/param' # the path to save the parameters
TRA_DIR = LOG_NAME_SAVE + '/trajectory.csv' # the path to save trajectory

#the path to reload weights, monitor and params
LOG_NAME_READ = 'log'
critic_weights_path = LOG_NAME_READ + '/model/ep' + str(RESTART_EP) + 'Critic_model.h5'
actor_weights_path = LOG_NAME_READ + '/model/ep' + str(RESTART_EP) + 'Actor_model.h5'
state_encoder_weights_path = LOG_NAME_READ + '/model/ep' + str(RESTART_EP) + 'StateEncoder.h5'
inverse_model_weights_path = LOG_NAME_READ + '/model/ep' + str(RESTART_EP) + 'InverseModel.h5'
forward_model_weights_path = LOG_NAME_READ + '/model/ep' + str(RESTART_EP) + 'ForwardModel.h5'

monitor_path = LOG_NAME_READ + '/monitor/'+ str(RESTART_EP)
params_json = LOG_NAME_READ + '/param/' + str(RESTART_EP) + '.json'
