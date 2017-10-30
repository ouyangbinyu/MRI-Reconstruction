import sys
import os

from datetime import datetime

from keras.models import Model
from keras.layers import Input, Dense, Activation
from keras.layers.convolutional import Conv2D
from keras.layers.pooling import MaxPooling2D
from keras.losses import mean_squared_error
from keras.optimizers import RMSProp
from keras.initializers import RandomNormal
from keras.callbacks import ModelCheckpoint

RMS_WEIGHT_DECAY = .9
LEARNING_RATE = .001
BATCH_SIZE = 32
NUM_EPOCHS = 2000

CHECKPOINT_FILE_PATH_FORMAT = "fnet-{epoch:02d}.hdf5"

class FNet:

	def __init__(self):
		self.architecture_exists = False

	def train(self, y_folded, y_original):
		"""
		Trains the specialized U-net for the MRI reconstruction task

		Parameters
		------------
		y_folded : [np.ndarray]
			A set of folded images obtained by subsampling k-space data
		y_original : [np.ndarray]
			The ground truth set of images, preprocessed by applying the inverse
			f_{cor} function and removing undersampled k-space data
		"""

		if not self.architecture_exists:
			self._create_architecture()

		checkpoint_callback = ModelCheckpoint(CHECKPOINT_FILE_PATH_FORMAT, monitor='val_loss', period=1)

		self.model.fit(y_folded, 
					   y_original, 
					   batch_size=BATCH_SIZE, 
					   nb_epoch=NUM_EPOCHS, 
					   shuffle=True, 
					   validation_split=.2,
					   verbose=1,
					   callbacks=[checkpoint_callback])


	def _get_initializer_seed(self):
		epoch = datetime.utcfromtimestamp(0)
		curr_time = datetime.now()
		millis_since_epoch = (curr_time - epoch).total_seconds() * 1000
		return int(millis_since_epoch)

	def _create_architecture(self):
		# How many channels does each image have? This should have a third dimension
		inputs = Input(shape=(256,256))

		weights_initializer = RandomNormal(mean=0.0, stddev=.01, seed=self._get_initializer_seed())

		# Using the padding=`same` option is equivalent to zero padding
		conv2d_1 = Conv2D(
			filters=64, kernel_size=(3,3), strides=(1,1), padding='same', 
			activation='relu', kernel_initializer=weights_initializer)(inputs)

		conv2d_2 = Conv2D(filters=64, kernel_size=(3,3), strides=(1,1), padding='same', 
			activation='relu', kernel_initializer=weights_initializer)(conv2d_1)

		maxpool_1 = MaxPooling2D(pool_size=(2,2), strides=(2,2), padding='same', 
			kernel_initializer=weights_initializer)(conv2d_2)

		conv2d_3 = Conv2D(filters=128, kernel_size=(3,3), strides=(1,1), padding='same', 
			activation='relu', kernel_initializer=weights_initializer)(maxpool_1)

		conv2d_4 = Conv2D(filters=128, kernel_size=(3,3), strides=(1,1), padding='same', 
			activation='relu', kernel_initializer=weights_initializer)(conv2d_3)

		maxpool_2 = MaxPooling2D(pool_size=(2,2), strides=(2,2), padding='same', 
			kernel_initializer=weights_initializer)(conv2d_4)

		conv2d_5 = Conv2D(filters=256, kernel_size=(3,3), strides=(1,1), padding='same', 
			activation='relu', kernel_initializer=weights_initializer)(maxpool_2)

		conv2d_6 = Conv2D(filters=128, kernel_size=(3,3), strides=(1,1), padding='same', 
			activation='relu', kernel_initializer=weights_initializer)(conv2d_5)

		deconv2d_1 = concatenate(
			[Conv2DTranspose(filters=128, kernel_size=(2, 2), strides=(2, 2), padding='same', 
				kernel_initializer=weights_initializer)(conv2d_6), conv2d_4], axis=3)

		conv2d_7 = Conv2D(filters=128, kernel_size=(3,3), strides=(1,1), padding='same', 
			activation='relu', kernel_initializer=weights_initializer)(deconv2d_1)

		conv2d_8 = Conv2D(filters=64, kernel_size=(3,3), strides=(1,1), padding='same', 
			activation='relu', kernel_initializer=weights_initializer)(conv2d_7)

		deconv2d_1 = concatenate(
			[Conv2DTranspose(filters=64, kernel_size=(2, 2), strides=(2, 2), padding='same', 
				kernel_initializer=weights_initializer)(conv2d_8), conv2d_2], axis=3)

		conv2d_9 = Conv2D(filters=64, kernel_size=(3,3), strides=(1,1), padding='same', 
			activation='relu', kernel_initializer=weights_initializer)(deconv2d_1)
		conv2d_10 = Conv2D(filters=64, kernel_size=(3,3), strides=(1,1), padding='same', 
			activation='relu', kernel_initializer=weights_initializer)(conv2d_9)

		# Conv2d_10 is 256 x 256 x 64. We now need to reduce the number of output
		# channels via a convolution with `n` filters, where `n` is the original
		# number of channels

		outputs = Conv2D(filters=256, kernel_size=(1,1), strides=(1,1), padding='same', 
			activation=None, kernel_initializer=weights_initializer)(deconv2d_1)

		optimizer = RMSProp(lr=LEARNING_RATE, rho=RMS_WEIGHT_DECAY, epsilon=0, decay=0)

		self.model = Model(inputs=[inputs], outputs=[outputs])
		self.model.compile(optimizer=optimizer, loss=mean_squared_error, metrics=[mean_squared_error])

		self.architecture_exists = True