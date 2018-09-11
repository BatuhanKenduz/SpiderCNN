import tensorflow as tf
from tensorflow.python.framework import ops
import numpy as np
import math
import sys
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, '../utils'))
sys.path.append(os.path.join(BASE_DIR, '../tf_ops/sampling'))
sys.path.append(os.path.join(BASE_DIR, '../tf_ops/grouping'))

import tf_util
from tf_grouping import query_ball_point, group_point, knn_point
from tf_sampling import farthest_point_sample, gather_point




def get_model(xyz_withnor, is_training, bn_decay=None, num_classes=40):
    batch_size = xyz_withnor.get_shape()[0].value
    num_point = xyz_withnor.get_shape()[1].value

    K_knn = 20
    taylor_channel = 3

    xyz = xyz_withnor[:, :, 0:3]
    
    with tf.variable_scope('delta') as sc:
        _, idx = knn_point(K_knn, xyz, xyz)
        
        grouped_xyz = group_point(xyz, idx)   
        point_cloud_tile = tf.expand_dims(xyz, [2])
        point_cloud_tile = tf.tile(point_cloud_tile, [1, 1, K_knn, 1])
        delta = grouped_xyz - point_cloud_tile

    with tf.variable_scope('SpiderConv1') as sc:
        feat_1 = tf_util.spiderConv(xyz_withnor, idx, delta, 32, taylor_channel = taylor_channel, 
                                        bn=True, is_training=is_training, bn_decay=bn_decay)

    with tf.variable_scope('SpiderConv2') as sc:
        feat_2 = tf_util.spiderConv(feat_1, idx, delta, 64, taylor_channel = taylor_channel, 
                                        bn=True, is_training=is_training, bn_decay=bn_decay)

    with tf.variable_scope('SpiderConv3') as sc:
        feat_3 = tf_util.spiderConv(feat_2, idx, delta, 128, taylor_channel = taylor_channel, 
                                        bn=True, is_training=is_training, bn_decay=bn_decay)

    with tf.variable_scope('SpiderConv4') as sc:
        feat_4 = tf_util.spiderConv(feat_3, idx, delta, 256, taylor_channel = taylor_channel, 
                                        bn=True, is_training=is_training, bn_decay=bn_decay)


    feat = tf.concat([feat_1, feat_2, feat_3, feat_4], 2)

    #top-k pooling
    net = tf_util.topk_pool(feat, k = 2, scope='topk_pool')
    
    net = tf.reshape(net, [batch_size, -1])
    net = tf_util.fully_connected(net, 512, bn=True, is_training=is_training,
                                  scope='fc1', bn_decay=bn_decay)
    net = tf_util.dropout(net, keep_prob=0.5, is_training=is_training,
                          scope='dp1')
    net = tf_util.fully_connected(net, 256, bn=True, is_training=is_training,
                                  scope='fc2', bn_decay=bn_decay)
    net = tf_util.dropout(net, keep_prob=0.5, is_training=is_training,
                          scope='dp2')
    net = tf_util.fully_connected(net, 40, activation_fn=None, scope='fc3')

    return net


def get_loss(pred, label):
    """ pred: B*NUM_CLASSES,
        label: B, """
    loss = tf.nn.sparse_softmax_cross_entropy_with_logits(logits=pred, labels=label)
    classify_loss = tf.reduce_mean(loss)
    tf.summary.scalar('classify loss', classify_loss)
    tf.add_to_collection('losses', classify_loss)

    return classify_loss


if __name__=='__main__':
    with tf.Graph().as_default():
        inputs = tf.zeros((32,1024,6))
        outputs = get_model(inputs, tf.constant(True))
        print(outputs)
