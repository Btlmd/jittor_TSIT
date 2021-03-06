#!/usr/bin/env bash

unset LD_LIBRARY_PATH

set -x

NAME='sis_landscape'
TASK='SIS'
DATA='landscape'
CROOT='/dataset'
SROOT='/dataset'
CKPTROOT='./checkpoints'
WORKER=48

export CUDA_VISIBLE_DEVICES=0,1,2,3,4,5

mpirun -np 6 python3 train.py \
    --name $NAME \
    --task $TASK \
    --checkpoints_dir $CKPTROOT \
    --batchSize 30 \
    --dataset_mode $DATA \
    --croot $CROOT \
    --sroot $SROOT \
    --nThreads $WORKER \
    --gan_mode hinge \
    --num_upsampling_layers more \
    --use_vae \
    --alpha 1.0 \
    --display_freq 20 \
    --save_epoch_freq 5 \
    --niter 100 \
    --niter_decay 100 \
    --lr 0.0002 \
    --lambda_vgg 20 \
    --lambda_feat 10 \
    --which_epoch 115 \
    --continue_train \
    --remote "user@166.111.227.254:/ckpts" \
    --remote_port 22

