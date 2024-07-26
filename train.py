# -*- coding: utf-8 -*-

from __future__ import print_function, division

import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.optim import lr_scheduler
from torch.autograd import Variable
from torchvision import datasets, transforms
import torch.backends.cudnn as cudnn
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
#from PIL import Image
import copy
import time
import os
from model import two_view_net, three_view_net
from random_erasing import RandomErasing
from autoaugment import ImageNetPolicy, CIFAR10Policy
import yaml
import math
from shutil import copyfile
import imgaug.augmenters as iaa
from utils import update_average, get_model_list, load_network, save_network, make_weights_for_balanced_classes, AverageMeter
from image_folder import ImageFolder_iaa_selectID, ImageFolder_iaa_multi_weather
from torch.utils.tensorboard import SummaryWriter
import numpy as np
import random
#
# import wandb
# import socket
# import torch_optimizer
from circle_loss import CircleLoss, convert_label_to_similarity
version =  torch.__version__
#fp16
try:
    from apex.fp16_utils import *
    from apex import amp, optimizers
except ImportError: # will be 3.x series
    print('This is not an error. If you want to use low precision, i.e., fp16, please install the apex with cuda support (https://github.com/NVIDIA/apex) and update pytorch to 1.0')
######################################################################
# Options
# --------
parser = argparse.ArgumentParser(description='Training')
parser.add_argument('--gpu_ids',default='0', type=str,help='gpu_ids: e.g. 0  0,1,2  0,2')
parser.add_argument('--name',default='two_view', type=str, help='output model name')
parser.add_argument('--experiment_name',default='debug', type=str, help='log dir name')
parser.add_argument('--pool',default='avg', type=str, help='pool avg')
parser.add_argument('--data_dir',default='./data/train',type=str, help='training dir path')
parser.add_argument('--train_all', action='store_true', help='use all training data' )
parser.add_argument('--color_jitter', action='store_true', help='use color jitter in training' )
parser.add_argument('--batchsize', default=8, type=int, help='batchsize')
parser.add_argument('--stride', default=2, type=int, help='stride')
parser.add_argument('--pad', default=10, type=int, help='padding')
parser.add_argument('--h', default=384, type=int, help='height')
parser.add_argument('--w', default=384, type=int, help='width')
parser.add_argument('--views', default=2, type=int, help='the number of views')
parser.add_argument('--erasing_p', default=0, type=float, help='Random Erasing probability, in [0,1]')
parser.add_argument('--use_dense', action='store_true', help='use densenet121' )
parser.add_argument('--use_vgg', action='store_true', help='use vgg16' )
parser.add_argument('--use_res101', action='store_true', help='use vgg16' )
parser.add_argument('--use_NAS', action='store_true', help='use NAS' )
parser.add_argument('--warm_epoch', default=0, type=int, help='the first K epoch that needs warm up')
parser.add_argument('--lr', default=0.01, type=float, help='learning rate')
parser.add_argument('--moving_avg', default=1.0, type=float, help='moving average')
parser.add_argument('--droprate', default=0.75, type=float, help='drop rate')
parser.add_argument('--DA', action='store_true', help='use Color Data Augmentation' )
parser.add_argument('--resume', action='store_true', help='use resume trainning' )
parser.add_argument('--share', action='store_true', help='share weight between different view' )
parser.add_argument('--extra_Google', action='store_true', help='using extra noise Google' )
parser.add_argument('--LPN', action='store_true', help='use LPN' )
parser.add_argument('--iaa', action='store_true', help='use iaa' )
parser.add_argument('--circle', action='store_true', help='use Circle loss' )
parser.add_argument('--block', default=4, type=int, help='the num of block' )
parser.add_argument('--fp16', action='store_true', help='use float16 instead of float32, which will save about 50% memory' )
parser.add_argument('--seed', default=1, type=int, help='random seed')
parser.add_argument('--norm', default='bn', type=str, help='selecting norm from [bn, ibn, spade]')
parser.add_argument('--multi_weather', action='store_true', help='use multiple weather' )
parser.add_argument('--adain',default='a',type=str, help='the mode of adain: a or b')
parser.add_argument('--conv_norm',default='none',type=str, help='none, in, ln')
parser.add_argument('--style_loss', action='store_true', help='use style loss')
parser.add_argument('--btnk', nargs='+', type=int, default=[1,0,1], help='determining the btnk')
parser.add_argument('--alpha', default=1, type=float, help='weight of two losses' )
parser.add_argument('--fname', default='train.txt', type=str, help='Name of log txt')
opt = parser.parse_args()

class CenterLoss(nn.Module):
    """Center loss.

    Reference:
    Wen et al. A Discriminative Feature Learning Approach for Deep Face Recognition. ECCV 2016.#

    Args:
        num_classes (int): number of classes.
        feat_dim (int): feature dimension.
    """

    def __init__(self, num_classes=10, feat_dim=2, use_gpu=True):
        super(CenterLoss, self).__init__()
        self.num_classes = num_classes
        self.feat_dim = feat_dim
        self.use_gpu = use_gpu

        if self.use_gpu:
            self.centers = nn.Parameter(torch.randn(self.num_classes, self.feat_dim).cuda())
        else:
            self.centers = nn.Parameter(torch.randn(self.num_classes, self.feat_dim))

    def forward(self, x, labels):
        """
        Args:
            x: feature matrix with shape (batch_size, feat_dim).
            labels: ground truth labels with shape (batch_size).
        """
        batch_size = x.size(0)
        distmat = torch.pow(x, 2).sum(dim=1, keepdim=True).expand(batch_size, self.num_classes) + \
                  torch.pow(self.centers, 2).sum(dim=1, keepdim=True).expand(self.num_classes, batch_size).t()
        # distmat.addmm_(1, -2, x, self.centers.t())
        distmat.addmm_(x, self.centers.t(), beta=1, alpha=-2)#

        classes = torch.arange(self.num_classes).long()
        if self.use_gpu: classes = classes.cuda()
        labels = labels.unsqueeze(1).expand(batch_size, self.num_classes)
        mask = labels.eq(classes.expand(batch_size, self.num_classes))

        dist = distmat * mask.float()
        loss = dist.clamp(min=1e-12, max=1e+12).sum() / batch_size

        return loss

if opt.resume:
    model, opt, start_epoch = load_network(opt.name, opt)
else:
    start_epoch = 0

fp16 = opt.fp16
data_dir = opt.data_dir
name = opt.name
str_ids = opt.gpu_ids.split(',')
gpu_ids = []
for str_id in str_ids:
    gid = int(str_id)
    if gid >=0:
        gpu_ids.append(gid)
# btnk_on = opt.btnk.split(',')
# btnks = []
# for on in btnk_on:
#     btnk.append(int(on))
print('btnk:-------------------', opt.btnk)
def seed_torch(seed=0):
    random.seed(seed)
    # os.environ['PYTHONHASHSEED'] = str(seed) # 为了禁止hash随机化，使得实验可复现
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    # torch.cuda.manual_seed_all(seed) # if you are using multi-GPU.
    # torch.backends.cudnn.benchmark = False
    # torch.backends.cudnn.deterministic = True


if opt.seed > 0:
    print('random seed---------------------:', opt.seed)
    seed_torch(seed = opt.seed)

# set gpu ids
if len(gpu_ids)>0:
    # torch.cuda.set_device(gpu_ids[0])
    os.environ['CUDA_VISIBLE_DEVICES'] = ','.join(map(str,gpu_ids))
    cudnn.benchmark = True
######################################################################
# Load Data
# ---------
#

transform_train_list = [
        #transforms.RandomResizedCrop(size=(opt.h, opt.w), scale=(0.75,1.0), ratio=(0.75,1.3333), interpolation=3), #Image.BICUBIC)
        transforms.Resize((opt.h, opt.w), interpolation=3),
        transforms.Pad( opt.pad, padding_mode='edge'),
        transforms.RandomCrop((opt.h, opt.w)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]

transform_satellite_list = [
        transforms.Resize((opt.h, opt.w), interpolation=3),
        transforms.Pad( opt.pad, padding_mode='edge'),
        transforms.RandomAffine(90),
        transforms.RandomCrop((opt.h, opt.w)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]

transform_val_list = [
        transforms.Resize(size=(opt.h, opt.w),interpolation=3), #Image.BICUBIC
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]
if opt.iaa:
    print('-----------------using iaa to augment the drone image----------------------------')
    iaa_drone_transform = iaa.Sequential([
        iaa.Resize({"height":opt.h, "width":opt.w}, interpolation=3),
        iaa.Pad(px=opt.pad, pad_mode="edge", keep_size=False),
        iaa.CropToFixedSize(width=opt.w, height=opt.h),
        iaa.Fliplr(0.5),
    ])

    iaa_weather_list = [
        None,
        iaa.Sequential([
            iaa.CloudLayer(intensity_mean=225, intensity_freq_exponent=-2, intensity_coarse_scale=2, alpha_min=1.0,
                           alpha_multiplier=0.9, alpha_size_px_max=10, alpha_freq_exponent=-2, sparsity=0.9,
                           density_multiplier=0.5, seed=35),
            iaa.AdditiveGaussianNoise(scale=(0, 0.05 * 255), seed=56)

        ]),
        iaa.Sequential([
            iaa.Rain(drop_size=(0.05, 0.1), speed=(0.04, 0.06), seed=38),
            iaa.Rain(drop_size=(0.05, 0.1), speed=(0.04, 0.06), seed=35),
            iaa.Rain(drop_size=(0.1, 0.2), speed=(0.04, 0.06), seed=73),
            iaa.Rain(drop_size=(0.1, 0.2), speed=(0.04, 0.06), seed=93),
            iaa.Rain(drop_size=(0.05, 0.2), speed=(0.04, 0.06), seed=95),
            iaa.AdditiveGaussianNoise(scale=(0, 0.05 * 255), seed=456)
        ]),
        iaa.Sequential([
            iaa.Snowflakes(flake_size=(0.5, 0.8), speed=(0.007, 0.03), seed=38),
            iaa.Snowflakes(flake_size=(0.5, 0.8), speed=(0.007, 0.03), seed=35),
            iaa.Snowflakes(flake_size=(0.6, 0.9), speed=(0.007, 0.03), seed=74),
            iaa.Snowflakes(flake_size=(0.6, 0.9), speed=(0.007, 0.03), seed=94),
            iaa.Snowflakes(flake_size=(0.5, 0.9), speed=(0.007, 0.03), seed=96),
            iaa.AdditiveGaussianNoise(scale=(0, 0.05 * 255), seed=148)
        ]),
        iaa.Sequential([
            iaa.BlendAlpha(0.5, foreground=iaa.Add(100), background=iaa.Multiply(0.2), seed=31),
            iaa.MultiplyAndAddToBrightness(mul=0.2, add=(-30, -15), seed=1991),
            iaa.AdditiveGaussianNoise(scale=(0, 0.05 * 255), seed=756)
        ]),
        iaa.Sequential([
            iaa.MultiplyAndAddToBrightness(mul=1.6, add=(0, 30), seed=1992),
            iaa.AdditiveGaussianNoise(scale=(0, 0.05 * 255), seed=158)
        ]),
        iaa.Sequential([
            iaa.CloudLayer(intensity_mean=225, intensity_freq_exponent=-2, intensity_coarse_scale=2, alpha_min=1.0,
                           alpha_multiplier=0.9, alpha_size_px_max=10, alpha_freq_exponent=-2, sparsity=0.9,
                           density_multiplier=0.5, seed=35),
            iaa.Rain(drop_size=(0.05, 0.2), speed=(0.04, 0.06), seed=35),
            iaa.Rain(drop_size=(0.05, 0.2), speed=(0.04, 0.06), seed=36),
            iaa.AdditiveGaussianNoise(scale=(0, 0.05 * 255), seed=4562)
        ]),
        iaa.Sequential([
            iaa.CloudLayer(intensity_mean=225, intensity_freq_exponent=-2, intensity_coarse_scale=2, alpha_min=1.0,
                           alpha_multiplier=0.9, alpha_size_px_max=10, alpha_freq_exponent=-2, sparsity=0.9,
                           density_multiplier=0.5, seed=35),
            iaa.Snowflakes(flake_size=(0.5, 0.9), speed=(0.007, 0.03), seed=35),
            iaa.Snowflakes(flake_size=(0.5, 0.9), speed=(0.007, 0.03), seed=36),
            iaa.AdditiveGaussianNoise(scale=(0, 0.05 * 255), seed=751)
        ]),
        iaa.Sequential([
            iaa.Snowflakes(flake_size=(0.5, 0.8), speed=(0.007, 0.03), seed=35),
            iaa.Rain(drop_size=(0.05, 0.1), speed=(0.04, 0.06), seed=35),
            iaa.Rain(drop_size=(0.1, 0.2), speed=(0.04, 0.06), seed=92),
            iaa.Rain(drop_size=(0.05, 0.2), speed=(0.04, 0.06), seed=91),
            iaa.Snowflakes(flake_size=(0.6, 0.9), speed=(0.007, 0.03), seed=74),
            iaa.AdditiveGaussianNoise(scale=(0, 0.05 * 255), seed=356)
        ]),
        iaa.Sequential([
            iaa.MotionBlur(15, seed=17),
            iaa.AdditiveGaussianNoise(scale=(0, 0.05 * 255), seed=86)
        ])
    ]

    transform_iaa_drone_list = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

if opt.erasing_p>0:
    transform_train_list = transform_train_list +  [RandomErasing(probability = opt.erasing_p, mean=[0.0, 0.0, 0.0])]

if opt.color_jitter:
    transform_train_list = [transforms.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1, hue=0)] + transform_train_list
    transform_satellite_list = [transforms.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1, hue=0)] + transform_satellite_list

if opt.DA:
    transform_train_list = [ImageNetPolicy()] + transform_train_list

print(transform_train_list)
data_transforms = {
    'train': transforms.Compose( transform_train_list ),
    'val': transforms.Compose(transform_val_list),
    'satellite': transforms.Compose(transform_satellite_list) }


train_all = ''
if opt.train_all:
     train_all = '_all'

image_datasets = {}
image_datasets['satellite'] = datasets.ImageFolder(os.path.join(data_dir, 'satellite'),
                                          data_transforms['satellite'])
# image_datasets['satellite'] = ImageFolder_iaa(os.path.join(data_dir, 'satellite'),
#                                           data_transforms['satellite'], iaa_transform=iaa_color_transform)
image_datasets['street'] = datasets.ImageFolder(os.path.join(data_dir, 'street'),
                                          data_transforms['train'])
if opt.iaa:
    print('-----------------using iaa to augment the drone image----------------------------')
    if opt.multi_weather:
        print('-----------------using multiple weather to augment the drone image----------------------------')
        image_datasets['drone'] = ImageFolder_iaa_multi_weather(os.path.join(data_dir, 'drone'), transform=transform_iaa_drone_list,
                                                iaa_transform=iaa_drone_transform, iaa_weather_list=iaa_weather_list, batchsize=opt.batchsize, shuffle=True, norm=opt.norm, select=True)
    else:
        image_datasets['drone'] = ImageFolder_iaa_selectID(os.path.join(data_dir, 'drone'), transform=transform_iaa_drone_list,
                                                iaa_transform=iaa_drone_transform, norm=opt.norm)

else:
    image_datasets['drone'] = datasets.ImageFolder(os.path.join(data_dir, 'drone'),
                                              data_transforms['train'])
image_datasets['google'] = datasets.ImageFolder(os.path.join(data_dir, 'google'),
                                          data_transforms['train'])


# def _init_fn(worker_id):
#     np.random.seed(int(opt.seed)+worker_id)
# if opt.seed > 0:
#     dataloaders = {x: torch.utils.data.DataLoader(image_datasets[x], batch_size=opt.batchsize,
#                                                 shuffle=True, num_workers=4, pin_memory=False, worker_init_fn=_init_fn)
#                 for x in ['satellite', 'street', 'drone', 'google']}
# else:
dataloaders = {x: torch.utils.data.DataLoader(image_datasets[x], batch_size=opt.batchsize,
                                            shuffle=True, num_workers=8, pin_memory=False) # 8 workers may work faster
            for x in ['satellite', 'street', 'drone', 'google']}
dataset_sizes = {x: len(image_datasets[x]) for x in ['satellite', 'street', 'drone', 'google']}
class_names = image_datasets['street'].classes
print(dataset_sizes)
# if not opt.resume:
#     with open(os.path.join('model',opt.name,opt.fname),'a',encoding='utf-8') as f:
#         text = str(dataset_sizes)+'\n'
#         f.write(text)
use_gpu = torch.cuda.is_available()

######################################################################
# Training the model
# ------------------
#
# Now, let's write a general function to train a model. Here, we will
# illustrate:
#
# -  Scheduling the learning rate
# -  Saving the best model
#
# In the following, parameter ``scheduler`` is an LR scheduler object from
# ``torch.optim.lr_scheduler``.

y_loss = {} # loss history
y_loss['train'] = []
y_loss['val'] = []
y_err = {}
y_err['train'] = []
y_err['val'] = []

def one_LPN_output(outputs, labels, criterion, block):
    # part = {}
    sm = nn.Softmax(dim=1)
    num_part = block
    score = 0
    loss = 0
    for i in range(num_part):
        part = outputs[i]
        score += sm(part)
        loss += criterion(part, labels)

    _, preds = torch.max(score.data, 1)

    return preds, loss


class ContrastiveLoss(nn.Module):
    def __init__(self, batch_size, device='cuda', temperature=0.5):
        super().__init__()
        self.batch_size = batch_size
        self.register_buffer("temperature", torch.tensor(temperature).to(device))  # 超参数 温度
        self.register_buffer("negatives_mask", (
            ~torch.eye(batch_size * 2, batch_size * 2, dtype=bool).to(device)).float())  # 主对角线为0，其余位置全为1的mask矩阵

    def forward(self, emb_i, emb_j):  # emb_i, emb_j 是来自同一图像的两种不同的预处理方法得到
        z_i = F.normalize(emb_i, dim=1)  # (bs, dim)  --->  (bs, dim)
        z_j = F.normalize(emb_j, dim=1)  # (bs, dim)  --->  (bs, dim)

        representations = torch.cat([z_i, z_j], dim=0)  # repre: (2*bs, dim)
        similarity_matrix = F.cosine_similarity(representations.unsqueeze(1), representations.unsqueeze(0),
                                                dim=2)  # simi_mat: (2*bs, 2*bs)

        sim_ij = torch.diag(similarity_matrix, self.batch_size)  # bs
        sim_ji = torch.diag(similarity_matrix, -self.batch_size)  # bs
        positives = torch.cat([sim_ij, sim_ji], dim=0)  # 2*bs

        nominator = torch.exp(positives / self.temperature)  # 2*bs
        denominator = self.negatives_mask * torch.exp(similarity_matrix / self.temperature)  # 2*bs, 2*bs

        loss_partial = -torch.log(nominator / torch.sum(denominator, dim=1))  # 2*bs
        loss = torch.sum(loss_partial) / (2 * self.batch_size)
        return loss


class InfoNCE(nn.Module):

    def __init__(self, loss_function, device='cuda' if torch.cuda.is_available() else 'cpu'):
        super().__init__()

        self.loss_function = loss_function
        self.device = device

    def forward(self, image_features1, image_features2, logit_scale):
        image_features1 = F.normalize(image_features1, dim=-1)
        image_features2 = F.normalize(image_features2, dim=-1)

        logits_per_image1 = logit_scale * image_features1 @ image_features2.T

        logits_per_image2 = logits_per_image1.T

        labels = torch.arange(len(logits_per_image1), dtype=torch.long, device=self.device)

        loss = (self.loss_function(logits_per_image1, labels) + self.loss_function(logits_per_image2, labels)) / 2

        return loss

def train_model(model, model_test, criterion, criterion_cent, optimizer, optimizer_centloss, scheduler, num_epochs=25, opt_pt=None, pt_scheduler=None):
    since = time.time()

    #best_model_wts = model.state_dict()
    cent_losses = AverageMeter()
    #best_acc = 0.0
    warm_up = 0.1 # We start from the 0.1*lrRate
    warm_iteration = round(dataset_sizes['satellite']/opt.batchsize)*opt.warm_epoch # first 5 epoch
    if opt.circle:
        criterion_circle = CircleLoss(m=0.25, gamma=64)
    # min_loss = 1.0
    #wandb初始化
    # wandb.init(config=opt,
    #            project="MuseNet",
    #            entity="teamwww",
    #            notes=socket.gethostname(),
    #            name="three_view_long_share_d0.5_256_lr0.001_210ep_weather_ConvNext_noStages3_LPN__block8",
    #            group="three_view_long_share_d0.5_256_lr0.001_210ep_weather_ConvNext_noStages3_LPN__block8",
    #            job_type="training")

    for epoch in range(num_epochs-start_epoch):
        epoch = epoch + start_epoch
        print('Epoch {}/{}'.format(epoch, num_epochs - 1))
        print('-' * 10)
        # with open(os.path.join('model',opt.name,opt.fname),'a',encoding='utf-8') as f:
        #     text = str('Epoch {}/{}'.format(epoch, num_epochs - 1))+'\n'+('-' * 10)+'\n'
        #     f.write(text)
        # Each epoch has a training and validation phase
        for phase in ['train']:
            if phase == 'train':
                model.train(True)  # Set model to training mode
            else:
                model.train(False)  # Set model to evaluate mode

            running_loss = 0.0
            running_corrects = 0.0
            running_corrects2 = 0.0
            running_corrects3 = 0.0
            if opt.circle:
                running_loss_ce = 0.0
                running_loss_cir = 0.0
            if opt.norm == 'spade':
                running_corrects_s_w = 0.0
                running_corrects_d_w = 0.0
                running_weather_loss = 0.0

            # Iterate over data.
            for data,data2,data3,data4 in zip(dataloaders['satellite'], dataloaders['street'], dataloaders['drone'], dataloaders['google']) :
                # get the inputs
                inputs, labels = data
                inputs2, labels2 = data2
                inputs4, labels4 = data4
                if opt.norm == 'spade':
                    inputs3, labels3, wlabels3 = data3
                    wlabels1 = torch.zeros_like(wlabels3)
                else:
                    inputs3, labels3 = data3
                now_batch_size,c,h,w = inputs.shape
                if now_batch_size<opt.batchsize: # skip the last batch
                    continue
                if use_gpu:
                    inputs = Variable(inputs.cuda().detach())
                    inputs2 = Variable(inputs2.cuda().detach())
                    inputs3 = Variable(inputs3.cuda().detach())
                    labels = Variable(labels.cuda().detach())
                    labels2 = Variable(labels2.cuda().detach())
                    labels3 = Variable(labels3.cuda().detach())
                    if opt.norm == 'spade':
                        wlabels3 = Variable(wlabels3.cuda().detach())
                        wlabels1 = Variable(wlabels1.cuda().detach())
                    if opt.extra_Google:
                        inputs4 = Variable(inputs4.cuda().detach())
                        labels4 = Variable(labels4.cuda().detach())
                else:
                    inputs, labels = Variable(inputs), Variable(labels)
 
                # zero the parameter gradients
                optimizer.zero_grad()
                if opt_pt != None:
                    opt_pt.zero_grad()

                # forward
                if phase == 'val':
                    with torch.no_grad():
                        outputs, outputs2 = model(inputs, inputs2)
                else:
                    if opt.views == 2: 
                        outputs, outputs2 = model(inputs, inputs2)
                    elif opt.views == 3:
                        # bug detection
                        # torch.autograd.set_detect_anomaly(True)
                        if opt.extra_Google:
                            
                            if opt.norm == 'spade':
                                outputs, outputs2, outputs3, outputs4, sout_w, dout_w = model(inputs, inputs2, inputs3, inputs4)
                            else:
                                outputs, outputs2, outputs3, outputs4 = model(inputs, inputs2, inputs3, inputs4)
                        else:
                            # outputs, outputs2, outputs3 = model(inputs, inputs2, inputs3)
                            outputs, outputs1_global, outputs2, outputs2_global, outputs3, outputs3_global = model(inputs, inputs2, inputs3)

                if not opt.LPN:
                    _, preds = torch.max(outputs.data, 1)
                    _, preds2 = torch.max(outputs2.data, 1)
                    
                    if opt.views == 2:
                        loss = criterion(outputs, labels) + criterion(outputs2, labels2)
                    elif opt.views == 3:
                        _, preds3 = torch.max(outputs3.data, 1)
                        loss = criterion(outputs, labels) + 1*criterion(outputs2, labels2) + criterion(outputs3, labels3)
                        if opt.extra_Google:
                            loss = loss + 1*criterion(outputs4, labels4)
                        if opt.norm == 'spade':
                            _, s_pred_w = torch.max(sout_w.data, 1)
                            _, d_pred_w = torch.max(dout_w.data, 1)
                            loss_s = criterion(sout_w, wlabels1)
                            loss_d = criterion(dout_w, wlabels3)
                            loss_w = opt.alpha*(loss_d + loss_s)
                            loss = loss + loss_w

                else:
                    # loss_global = criterion(outputs1_global, labels) + criterion(outputs3_global, labels3)
                    # loss_global = loss_func(outputs3_global, outputs1_global, model.logit_scale.exp())
                    loss_cent = criterion_cent(outputs1_global, labels) + criterion_cent(outputs3_global, labels3)  # center loss 自己添加 6.21#
                    # print('------------------------using LPN--------------------------------')
                    preds, loss = one_LPN_output(outputs, labels, criterion, opt.block)
                    preds2, loss2 = one_LPN_output(outputs2, labels2, criterion, opt.block)

                    if opt.views == 2:       # no implement this LPN model
                        loss = loss + loss2
                    elif opt.views == 3:
                        preds3, loss3 = one_LPN_output(outputs3, labels3, criterion, opt.block)
                        loss = loss + loss3 + loss_cent
                        if opt.extra_Google:
                            _, loss4 = one_LPN_output(outputs4, labels4, criterion, opt.block)
                            loss = loss + loss4
                        # if opt.norm == 'spade':
                        #     _, s_pred_w = torch.max(sout_w.data, 1)
                        #     _, d_pred_w = torch.max(dout_w.data, 1)
                        #     loss_s = criterion(sout_w, wlabels1)
                        #     loss_d = criterion(dout_w, wlabels3)
                        #     loss_w = 1*(loss_d + loss_s)
                        #     loss = loss + loss_w

                # backward + optimize only if in training phase
                if epoch<opt.warm_epoch and phase == 'train': 
                    warm_up = min(1.0, warm_up + 0.9 / warm_iteration)
                    loss *= warm_up

                if phase == 'train':
                    if fp16: # we use optimier to backward loss
                        with amp.scale_loss(loss, optimizer) as scaled_loss:
                            scaled_loss.backward()
                    else:
                        # with torch.autograd.detect_anomaly():
                        loss.backward()
                    optimizer.step()

                    # by doing so, weight_cent would not impact on the learning of centers
                    for param in criterion_cent.parameters():
                        param.grad.data *= (1. / 1)
                    optimizer_centloss.step()
                    cent_losses.update(loss_cent.item(), labels.size(0))

                    # ema_model.update(model)
                    if opt_pt != None:
                        opt_pt.step()
                    ##########
                    if opt.moving_avg<1.0:
                        update_average(model_test, model, opt.moving_avg)

                # statistics
                if int(version[0])>0 or int(version[2]) > 3: # for the new version like 0.4.0, 0.5.0 and 1.0.0
                    running_loss += loss.item() * now_batch_size
                else :  # for the old version like 0.3.0 and 0.3.1
                    running_loss += loss.data[0] * now_batch_size
                running_corrects += float(torch.sum(preds == labels.data))
                running_corrects2 += float(torch.sum(preds2 == labels2.data))
                if opt.views == 3:
                    running_corrects3 += float(torch.sum(preds3 == labels3.data))
                if opt.norm=='spade':
                    running_weather_loss += loss_w.item() * now_batch_size
                    running_corrects_s_w += float(torch.sum(s_pred_w == wlabels1))
                    running_corrects_d_w += float(torch.sum(d_pred_w == wlabels3))


            epoch_loss = running_loss / dataset_sizes['satellite']
            epoch_acc = running_corrects / dataset_sizes['satellite']
            epoch_acc2 = running_corrects2 / dataset_sizes['satellite']
            if opt.norm == 'spade':
                epoch_weather_loss = running_weather_loss / dataset_sizes['satellite']
                epoch_acc_sw = running_corrects_s_w / dataset_sizes['satellite']
                epoch_acc_dw = running_corrects_d_w / dataset_sizes['satellite']

            if opt.views == 2:
                print('{} Loss: {:.4f} Satellite_Acc: {:.4f}  Street_Acc: {:.4f}'.format(phase, epoch_loss, epoch_acc, epoch_acc2))
            elif opt.views == 3:
                epoch_acc3 = running_corrects3 / dataset_sizes['satellite']
                if opt.norm == 'spade':
                   
                    print('{} Loss: {:.4f} Satellite_Acc: {:.4f}  Street_Acc: {:.4f} Drone_Acc: {:.4f} WeatherLoss: {:.4f} W_S_Acc: {:.4f} W_D_Acc: {:.4f}'.format(phase,
                                                                                                                   epoch_loss,
                                                                                                                   epoch_acc,
                                                                                                                   epoch_acc2,
                                                                                                                  epoch_acc3, epoch_weather_loss, epoch_acc_sw, epoch_acc_dw))
                else:
                    # print('{} Loss: {:.4f} Satellite_Acc: {:.4f}  Street_Acc: {:.4f} Drone_Acc: {:.4f}'.format(phase, epoch_loss, epoch_acc, epoch_acc2, epoch_acc3))
                    print('{} Loss: {:.4f} loss_center: {:.4f} Satellite_Acc: {:.4f} Drone_Acc: {:.4f}'.format(phase, epoch_loss, cent_losses.avg, epoch_acc, epoch_acc3))
                    # with open(os.path.join('model', opt.name, opt.fname), 'a', encoding='utf-8') as f:
                    #     text = str(
                    #         '{} Loss: {:.4f} Satellite_Acc: {:.4f} Drone_Acc: {:.4f} '
                    #         .format(phase, epoch_loss, epoch_acc, epoch_acc3)) + '\n'
                    #     f.write(text)

            #use wandb
            # wandb.log({"train_loss": epoch_loss, "Satellite_Acc": epoch_acc, "Drone_Acc": epoch_acc3})

            writer.add_scalar('Train Loss', epoch_loss, epoch+1)
          
            if opt.norm == 'spade':
                #writer.add_scalar('Pt_MLP_Lr', optimizer.param_groups[3]['lr'], epoch+1)
                writer.add_scalar('weather_loss', epoch_weather_loss, epoch + 1)
            y_loss[phase].append(epoch_loss)
            y_err[phase].append(1.0-epoch_acc)            
            # deep copy the model
            if phase == 'train':
                scheduler.step()
                if pt_scheduler != None:
                    pt_scheduler.step()
            last_model_wts = model.state_dict()
            if epoch > 200 and (epoch+1) % 10 == 0:
                save_network(model, opt.name, epoch)
                # ema_weight = utils.get_state_dict(ema_model)#
                # each_epoch_path = os.path.join('./model', opt.name, 'net_209')
                # torch.save(ema_weight, f"{each_epoch_path}_ema.pth")
            #draw_curve(epoch)

            # if epoch >= 90 and epoch_loss < min_loss:
            #     save_network(model, opt.name, epoch)
            #     min_loss = epoch_loss

        time_elapsed = time.time() - since
        print('Training complete in {:.0f}m {:.0f}s'.format(
            time_elapsed // 60, time_elapsed % 60))
        print()

    time_elapsed = time.time() - since
    print('Training complete in {:.0f}m {:.0f}s'.format(
        time_elapsed // 60, time_elapsed % 60))
    #print('Best val Acc: {:4f}'.format(best_acc))
    #save_network(model_test, opt.name+'adapt', epoch)

    return model


######################################################################
# Draw Curve
#---------------------------
x_epoch = []
fig = plt.figure()
ax0 = fig.add_subplot(121, title="loss")
ax1 = fig.add_subplot(122, title="top1err")
def draw_curve(current_epoch):
    x_epoch.append(current_epoch)
    ax0.plot(x_epoch, y_loss['train'], 'bo-', label='train')
    ax0.plot(x_epoch, y_loss['val'], 'ro-', label='val')
    ax1.plot(x_epoch, y_err['train'], 'bo-', label='train')
    ax1.plot(x_epoch, y_err['val'], 'ro-', label='val')
    if current_epoch == 0:
        ax0.legend()
        ax1.legend()
    fig.savefig( os.path.join('./model',name,'train.jpg'))


######################################################################
# Finetuning the convnet
# ----------------------
#
# Load a pretrainied model and reset final fully connected layer.
#

if opt.views == 2:
    if opt.LPN:
        model = two_view_net(len(class_names), droprate = opt.droprate, stride = opt.stride, pool = opt.pool, share_weight = opt.share, LPN = True)
    else:
        model = two_view_net(len(class_names), droprate = opt.droprate, stride = opt.stride, pool = opt.pool, share_weight = opt.share)
elif opt.views == 3:
    if opt.LPN:
        model = three_view_net(len(class_names), droprate = opt.droprate, stride = opt.stride, pool = opt.pool, share_weight = opt.share, LPN = True, block = opt.block, norm=opt.norm, btnk=opt.btnk)
    else:
        model = three_view_net(len(class_names), droprate = opt.droprate, stride = opt.stride, pool = opt.pool, share_weight = opt.share, norm = opt.norm, adain=opt.adain, circle=opt.circle, btnk=opt.btnk, conv_norm=opt.conv_norm, VGG16=opt.use_vgg, Dense=opt.use_dense, ResNet101=opt.use_res101)

opt.nclasses = len(class_names)

print(model)

criterion_cent = CenterLoss(num_classes=701, feat_dim=2, use_gpu=True)  # center loss 自己添加 6.21
optimizer_centloss = torch.optim.SGD(criterion_cent.parameters(), lr=0.005) #6.21
# ema_model = utils.ModelEmaV2(model, decay=0.9998, device=None)    #use ema
# ema_model = utils.ModelEmaV2(model, decay=0.1, device=None)    #use ema
# ema_model = ema_model.cuda()

# For resume:
if start_epoch>=40:
    opt.lr = opt.lr*0.1
if not opt.LPN:
    if opt.norm == 'spade':
        ignored_params = list(map(id, model.classifier.parameters()))
        ignored_params += list(map(id, model.pt_model.parameters()))
        base_params = filter(lambda p: id(p) not in ignored_params, model.parameters())

        pt_res_params = list(map(id, model.pt_model.model.parameters()))
        pt_res_params += list(map(id, model.pt_model.classifier.parameters()))
        pt_mlp_params = filter(lambda p: id(p) not in pt_res_params, model.pt_model.parameters())
        optimizer_ft = optim.SGD([
            {'params': base_params, 'lr': 0.1 * opt.lr},
            {'params': model.classifier.parameters(), 'lr': opt.lr},
            {'params': model.pt_model.model.parameters(), 'lr': 0.1 * opt.lr},
            {'params': pt_mlp_params, 'lr': opt.lr},
            {'params': model.pt_model.classifier.parameters(), 'lr': opt.lr}
        ], weight_decay=5e-4, momentum=0.9, nesterov=True)
        # optimizer_ft = torch_optimizer.Lamb([
        #     {'params': base_params, 'lr': 0.1 * opt.lr},
        #     {'params': model.classifier.parameters(), 'lr': opt.lr},
        #     {'params': model.pt_model.model.parameters(), 'lr': 0.1 * opt.lr},
        #     {'params': pt_mlp_params, 'lr': 0.1 * opt.lr},
        #     {'params': model.pt_model.classifier.parameters(), 'lr': opt.lr}
        # ])


        # optimizer_pt = optim.Adam([
        #     {'params': other_params, 'lr': 0.0001},
        #     {'params': model.model_1.pt_model.model.parameters(), 'lr': 0.00001}
        # ], betas=(0.9, 0.999), weight_decay=5e-4)

    else:
        ignored_params = list(map(id, model.classifier.parameters() ))
        base_params = filter(lambda p: id(p) not in ignored_params, model.parameters())
        optimizer_ft = optim.SGD([
                    {'params': base_params, 'lr': 0.1*opt.lr},
                    {'params': model.classifier.parameters(), 'lr': opt.lr}
                ], weight_decay=5e-4, momentum=0.9, nesterov=True)
        # optimizer_ft = torch_optimizer.Lamb([
        #     {'params': base_params, 'lr': 0.1 * opt.lr},
        #     {'params': model.classifier.parameters(), 'lr': opt.lr}
        # ])
else:
    if opt.norm == 'spade':
        ignored_params =list()
        for i in range(opt.block):
            cls_name = 'classifier'+str(i)
            c = getattr(model, cls_name)
            ignored_params += list(map(id, c.parameters() ))
        ignored_params += list(map(id, model.pt_model.parameters()))
        base_params = filter(lambda p: id(p) not in ignored_params, model.parameters())

        pt_res_params = list(map(id, model.pt_model.model.parameters()))
        pt_res_params += list(map(id, model.pt_model.classifier.parameters()))
        pt_mlp_params = filter(lambda p: id(p) not in pt_res_params, model.pt_model.parameters())
        optim_params = [
            {'params': base_params, 'lr': 0.1 * opt.lr},
            {'params': model.pt_model.model.parameters(), 'lr': 0.1 * opt.lr},
            {'params': pt_mlp_params, 'lr': opt.lr},
            {'params': model.pt_model.classifier.parameters(), 'lr': opt.lr}
        ]
        for i in range(opt.block):
            cls_name = 'classifier'+str(i)
            c = getattr(model, cls_name)
            optim_params.append({'params': c.parameters(), 'lr': opt.lr})
    else:
        ignored_params =list()
        for i in range(opt.block):
            cls_name = 'classifier'+str(i)
            c = getattr(model, cls_name)
            ignored_params += list(map(id, c.parameters() ))

        # ignored_params +=list(map(id, model.classifier.parameters()))   #使用global6.13
        base_params = filter(lambda p: id(p) not in ignored_params, model.parameters())

        optim_params = [{'params': base_params, 'lr': 0.1*opt.lr}, {'params': criterion_cent.parameters(), 'lr': 10*opt.lr}]   #6.25centerloss
        for i in range(opt.block):
            cls_name = 'classifier'+str(i)
            c = getattr(model, cls_name)
            optim_params.append({'params': c.parameters(), 'lr': opt.lr})
        # optim_params.append({'params': model.classifier.parameters(), 'lr': opt.lr})   ##使用global6.13

    optimizer_ft = optim.SGD(optim_params, weight_decay=5e-4, momentum=0.9, nesterov=True)

# Decay LR by a factor of 0.1 every 40 epochs
# exp_lr_scheduler = lr_scheduler.StepLR(optimizer_ft, step_size=100, gamma=0.1)
exp_lr_scheduler = lr_scheduler.MultiStepLR(optimizer_ft, milestones=[120, 180, 210], gamma=0.1)
# exp_lr_scheduler_pt = lr_scheduler.StepLR(optimizer_pt, step_size=80, gamma=0.1)

######################################################################
# Train and evaluate
# ^^^^^^^^^^^^^^^^^^
#
# It should take around 1-2 hours on GPU. 
#
log_dir = './log/' + opt.experiment_name
if not os.path.isdir(log_dir):
    os.mkdir(log_dir)
writer = SummaryWriter(log_dir)
dir_name = os.path.join('./model',name)
if not opt.resume:
    if not os.path.isdir(dir_name):
        os.mkdir(dir_name)
#record every run
    copyfile('./run.sh', dir_name+'/run.sh')
    copyfile('./train.py', dir_name+'/train.py')
    copyfile('./model.py', dir_name+'/model.py')
    copyfile('./resnet_spade.py', dir_name + '/resnet_spade.py')
# save opts
    with open('%s/opts.yaml'%dir_name,'w') as fp:
        yaml.dump(vars(opt), fp, default_flow_style=False)
# model to gpu
model = model.cuda()
if fp16:
    model, optimizer_ft = amp.initialize(model, optimizer_ft, opt_level = "O1")

criterion = nn.CrossEntropyLoss()
if opt.moving_avg<1.0:
    model_test = copy.deepcopy(model)
    num_epochs = 140
else:
    model_test = None
    num_epochs = 210
# criterion_cent = CenterLoss(num_classes=701, feat_dim=2, use_gpu=True)  # center loss 自己添加 6.21
# optimizer_centloss = torch.optim.SGD(criterion_cent.parameters(), lr=0.005) #6.21
model = train_model(model, model_test, criterion, criterion_cent, optimizer_ft, optimizer_centloss, exp_lr_scheduler,
                       num_epochs=num_epochs, opt_pt=None, pt_scheduler=None)
writer.close()
