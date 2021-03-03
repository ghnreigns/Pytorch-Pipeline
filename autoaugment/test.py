# -*- coding: utf-8 -*-

import argparse
import math
import os
import random
import time
import warnings
from collections import OrderedDict
from datetime import datetime
from glob import glob

import archs
import joblib
import losses
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.backends.cudnn as cudnn
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torchvision
from skimage.io import imread, imsave
from sklearn.model_selection import train_test_split
from torch.autograd import Variable
from torch.optim import lr_scheduler
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms
from tqdm import tqdm

from dataset import Dataset
from metrics import batch_iou, dice_coef, iou_score, mean_iou
from utils import count_params, str2bool


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('--name', default=None,
                        help='model name')

    args = parser.parse_args()

    return args


def main():
    val_args = parse_args()

    args = joblib.load('models/%s/args.pkl' %val_args.name)

    if not os.path.exists('output/%s' %args.name):
        os.makedirs('output/%s' %args.name)

    print('Config -----')
    for arg in vars(args):
        print('%s: %s' %(arg, getattr(args, arg)))
    print('------------')

    joblib.dump(args, 'models/%s/args.pkl' %args.name)

    # create model
    print("=> creating model %s" %args.arch)
    model = archs.__dict__[args.arch](args)

    model = model.cuda()

    # Data loading code
    img_paths = glob('input/' + args.dataset + '/images/*')
    mask_paths = glob('input/' + args.dataset + '/masks/*')

    train_img_paths, val_img_paths, train_mask_paths, val_mask_paths = \
        train_test_split(img_paths, mask_paths, test_size=0.2, random_state=41)

    model.load_state_dict(torch.load('models/%s/model.pth' %args.name))
    model.eval()

    val_dataset = Dataset(args, val_img_paths, val_mask_paths)
    val_loader = torch.utils.data.DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        pin_memory=True,
        drop_last=False)

    with warnings.catch_warnings():
        warnings.simplefilter('ignore')

        with torch.no_grad():
            for i, (input, target) in tqdm(enumerate(val_loader), total=len(val_loader)):
                input = input.cuda()
                target = target.cuda()

                # compute output
                if args.deepsupervision:
                    output = model(input)[-1]
                else:
                    output = model(input)

                output = torch.sigmoid(output).data.cpu().numpy()
                img_paths = val_img_paths[args.batch_size*i:args.batch_size*(i+1)]

                for i in range(output.shape[0]):
                    imsave('output/%s/'%args.name+os.path.basename(img_paths[i]), (output[i,0,:,:]*255).astype('uint8'))

        torch.cuda.empty_cache()

    # IoU
    ious = []
    for i in tqdm(range(len(val_mask_paths))):
        mask = imread(val_mask_paths[i])
        pb = imread('output/%s/'%args.name+os.path.basename(val_mask_paths[i]))

        mask = mask.astype('float32') / 255
        pb = pb.astype('float32') / 255

        '''
        plt.figure()
        plt.subplot(121)
        plt.imshow(mask)
        plt.subplot(122)
        plt.imshow(pb)
        plt.show()
        '''

        iou = iou_score(pb, mask)
        ious.append(iou)
    print('IoU: %.4f' %np.mean(ious))


if __name__ == '__main__':
    main()
