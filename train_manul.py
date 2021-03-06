import tensorflow as tf
import os
import glob
from matplotlib import pyplot as plt
# %matplotlib inline
import time
# tf.debugging.set_log_device_placement(True)

gpus = tf.config.experimental.list_logical_devices('GPU')

imgs_path = glob.glob('./data/train/*.png')

len(imgs_path)

import random

# img = tf.keras.preprocessing.image.load_img(random.choice(imgs_path))

print(imgs_path[:3])


def read_jpg(path):
    img = tf.io.read_file(path)
    img = tf.image.decode_jpeg(img, channels=3)
    return img


def normalize(input_image, input_mask):
    input_image = tf.cast(input_image, tf.float32) / 127.5 - 1
    input_mask = tf.cast(input_mask, tf.float32) / 127.5 - 1
    return input_image, input_mask


def load_image(image_path):
    image = read_jpg(image_path)
    w = tf.shape(image)[1]
    w = w // 2
    input_image = image[:, :w, :]
    input_mask = image[:, w:, :]
    input_image = tf.image.resize(input_image, (256, 256))
    input_mask = tf.image.resize(input_mask, (256, 256))

    if tf.random.uniform(()) > 0.5:
        input_image = tf.image.flip_left_right(input_image)
        input_mask = tf.image.flip_left_right(input_mask)

    input_image, input_mask = normalize(input_image, input_mask)

    return input_mask, input_image


dataset = tf.data.Dataset.from_tensor_slices(imgs_path)
train = dataset.map(load_image, num_parallel_calls=tf.data.experimental.AUTOTUNE)
BATCH_SIZE = 5  # batch_size32->5변경
BUFFER_SIZE = 500  # buffer_size 200->500변경

train_dataset = train.shuffle(BUFFER_SIZE).batch(BATCH_SIZE)
train_dataset = train_dataset.prefetch(buffer_size=tf.data.experimental.AUTOTUNE)

# plt.figure(figsize=(8, 5))
# for img, musk in train_dataset.take(1):
#     plt.subplot(1,2,1)
#     plt.imshow(tf.keras.preprocessing.image.array_to_img(img[0]))
#     plt.subplot(1,2,2)
#     plt.imshow(tf.keras.preprocessing.image.array_to_img(musk[0]))

imgs_path_test = glob.glob('./data/val/*.png')

print(len(imgs_path_test))

dataset_test = tf.data.Dataset.from_tensor_slices(imgs_path_test)


def load_image_test(image_path):
    image = read_jpg(image_path)
    w = tf.shape(image)[1]
    w = w // 2
    input_image = image[:, :w, :]
    input_mask = image[:, w:, :]
    input_image = tf.image.resize(input_image, (256, 256))
    input_mask = tf.image.resize(input_mask, (256, 256))

    input_image, input_mask = normalize(input_image, input_mask)

    return input_mask, input_image


dataset_test = dataset_test.map(load_image_test)
dataset_test = dataset_test.batch(BATCH_SIZE)

# for img, musk in dataset_test.take(1):
#     plt.subplot(1,2,1)
#     plt.imshow(tf.keras.preprocessing.image.array_to_img(img[0]))
#     plt.subplot(1,2,2)
#     plt.imshow(tf.keras.preprocessing.image.array_to_img(musk[0]))

OUTPUT_CHANNELS = 3


def downsample(filters, size, apply_batchnorm=True):
    #    initializer = tf.random_normal_initializer(0., 0.02)
    #    for Downsampling, use : Average Pooling, Conv2d +stride

    result = tf.keras.Sequential()
    result.add(
        tf.keras.layers.Conv2D(filters, size, strides=2, padding='same',
                               use_bias=False))
    # result.add(
    # tf.keras.layers.AveragePooling2D(pool_size()))

    if apply_batchnorm:
        result.add(tf.keras.layers.BatchNormalization())

        result.add(tf.keras.layers.LeakyReLU())

    return result


def upsample(filters, size, apply_dropout=False):
    #    initializer = tf.random_normal_initializer(0., 0.02)
    #    For Upsampling, use : PixelShuffle,ConvTranspose2d+stride
    result = tf.keras.Sequential()
    result.add(
        tf.keras.layers.Conv2DTranspose(filters, size, strides=2,
                                        padding='same',
                                        use_bias=False))

    result.add(tf.keras.layers.BatchNormalization())

    if apply_dropout:
        result.add(tf.keras.layers.Dropout(0.5))

    result.add(tf.keras.layers.LeakyReLU())  # activation function ReLU->LeakyReLU로 변경

    return result


def Generator():
    inputs = tf.keras.layers.Input(shape=[256, 256, 3])

    down_stack = [
        downsample(64, 4, apply_batchnorm=False),  # (bs, 128, 128, 64)
        downsample(128, 4),  # (bs, 64, 64, 128)
        downsample(256, 4),  # (bs, 32, 32, 256)
        downsample(512, 4),  # (bs, 16, 16, 512)
        downsample(512, 4),  # (bs, 8, 8, 512)
        downsample(512, 4),  # (bs, 4, 4, 512)
        downsample(512, 4),  # (bs, 2, 2, 512)
        downsample(512, 4),  # (bs, 1, 1, 512)
    ]

    up_stack = [
        upsample(512, 4, apply_dropout=True),  # (bs, 2, 2, 1024)
        upsample(512, 4, apply_dropout=True),  # (bs, 4, 4, 1024)
        upsample(512, 4, apply_dropout=True),  # (bs, 8, 8, 1024)
        upsample(512, 4),  # (bs, 16, 16, 1024)
        upsample(256, 4),  # (bs, 32, 32, 512)
        upsample(128, 4),  # (bs, 64, 64, 256)
        upsample(64, 4),  # (bs, 128, 128, 128)
    ]

    #    initializer = tf.random_normal_initializer(0., 0.02)
    last = tf.keras.layers.Conv2DTranspose(OUTPUT_CHANNELS, 4,
                                           strides=2,
                                           padding='same',
                                           activation='tanh')  # (bs, 256, 256, 3)

    x = inputs

    # Downsampling through the model
    skips = []
    for down in down_stack:
        x = down(x)
        skips.append(x)

    skips = reversed(skips[:-1])

    # Upsampling and establishing the skip connections
    for up, skip in zip(up_stack, skips):
        x = up(x)
        x = tf.keras.layers.Concatenate()([x, skip])

    x = last(x)

    return tf.keras.Model(inputs=inputs, outputs=x)


generator = Generator()

LAMBDA = 10


def generator_loss(disc_generated_output, gen_output, target):
    gan_loss = loss_object(tf.ones_like(disc_generated_output), disc_generated_output)

    # mean absolute error
    l1_loss = tf.reduce_mean(tf.abs(target - gen_output))

    total_gen_loss = gan_loss + (LAMBDA * l1_loss)

    return total_gen_loss, gan_loss, l1_loss


def Discriminator():
    #    initializer = tf.random_normal_initializer(0., 0.02)

    inp = tf.keras.layers.Input(shape=[256, 256, 3], name='input_image')
    tar = tf.keras.layers.Input(shape=[256, 256, 3], name='target_image')

    x = tf.keras.layers.concatenate([inp, tar])  # (bs, 256, 256, channels*2)

    down1 = downsample(64, 4, False)(x)  # (bs, 128, 128, 64)
    down2 = downsample(128, 4)(down1)  # (bs, 64, 64, 128)
    down3 = downsample(256, 4)(down2)  # (bs, 32, 32, 256)

    conv = tf.keras.layers.Conv2D(512, 4, strides=1,
                                  padding='same',
                                  use_bias=False)(down3)  # (bs, 32, 32, 512)

    batchnorm1 = tf.keras.layers.BatchNormalization()(conv)

    leaky_relu = tf.keras.layers.LeakyReLU()(batchnorm1)

    last = tf.keras.layers.Conv2D(1, 4, strides=1, padding='same')(leaky_relu)  # (bs, 30, 30, 1)

    return tf.keras.Model(inputs=[inp, tar], outputs=last)


discriminator = Discriminator()

loss_object = tf.keras.losses.BinaryCrossentropy(from_logits=True)


def discriminator_loss(disc_real_output, disc_generated_output):
    real_loss = loss_object(tf.ones_like(disc_real_output), disc_real_output)

    generated_loss = loss_object(tf.zeros_like(disc_generated_output), disc_generated_output)

    total_disc_loss = real_loss + generated_loss

    return total_disc_loss


generator_optimizer = tf.keras.optimizers.Adam(2e-4, beta_1=0.5)
discriminator_optimizer = tf.keras.optimizers.Adam(2e-4, beta_1=0.5)


def generate_images(model, test_input, tar, epoch):
    prediction = model(test_input, training=True)
    # plt.figure(figsize=(15,15))

    display_list = [test_input[0], tar[0], prediction[0]]
    title = ['Input Image', 'Ground Truth', 'Predicted Image']

    for i in range(3):
        plt.subplot(1, 3, i+1)
        plt.title(title[i])
    # getting the pixel values between [0, 1] to plot it.
        plt.imshow(display_list[i] * 0.5 + 0.5)
        plt.axis('off')
    plt.savefig('image_at_epoch_{:04d}.png'.format(epoch))


for example_input, example_target in dataset_test.take(1):
    generate_images(generator, example_input, example_target, 0)

EPOCHS = 5  # 임의로 test를 위해 5로 변경(다른 article에서는 40~50사이가 가장 좋았다는 의견있음


@tf.function
def train_step(input_image, target, epoch):
    with tf.GradientTape() as gen_tape, tf.GradientTape() as disc_tape:
        with tf.device(gpus[0].name):
            gen_output = generator(input_image, training=True)

            disc_real_output = discriminator([input_image, target], training=True)
            disc_generated_output = discriminator([input_image, gen_output], training=True)

            gen_total_loss, gen_gan_loss, gen_l1_loss = generator_loss(disc_generated_output, gen_output, target)
            disc_loss = discriminator_loss(disc_real_output, disc_generated_output)

    with tf.device(gpus[1].name):
        generator_gradients = gen_tape.gradient(gen_total_loss,
                                                generator.trainable_variables)
        discriminator_gradients = disc_tape.gradient(disc_loss,
                                                     discriminator.trainable_variables)

        generator_optimizer.apply_gradients(zip(generator_gradients,
                                                generator.trainable_variables))
        discriminator_optimizer.apply_gradients(zip(discriminator_gradients,
                                                    discriminator.trainable_variables))


def fit(train_ds, epochs, test_ds):
    for epoch in range(epochs + 1):  # 단계별 결과 확인을 위해 if문 삭제
        with tf.device(gpus[1].name):
            for example_input, example_target in test_ds.take(1):
                generate_images(generator, example_input, example_target, epoch)
            print("Epoch: ", epoch)

        with tf.device(gpus[0].name):
            for n, (input_image, target) in train_ds.enumerate():
                print('.', end='')
                train_step(input_image, target, epoch)
            print()


fit(train_dataset, EPOCHS, dataset_test)
