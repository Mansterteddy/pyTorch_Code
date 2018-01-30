'''Train CIFAR10 with PyTorch.'''
from __future__ import print_function
import os

import torch
import torch.nn as nn
import torch.optim as optim
from torch.autograd import Variable
import torch.nn.functional as F
import torch.backends.cudnn as cudnn
import torch.utils.model_zoo as model_zoo

import torchvision
import torchvision.models as models
import torchvision.transforms as transforms

import config
from models import *
from utils import *

use_cuda = torch.cuda.is_available()
best_acc = 0  # best val accuracy
best_epoch = 0
start_epoch = 0  # start from epoch 0 or last checkpoint epoch

train_path = "./data/train/"
val_path = "./data/val/"

# Data
print('==> Preparing data..')
transform = transforms.Compose([
    transforms.RandomSizedCrop(224),
    transforms.RandomHorizontalFlip(),
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
])

trainset = torchvision.datasets.ImageFolder(train_path, transform=transform)
trainloader = torch.utils.data.DataLoader(trainset, batch_size=64, shuffle=True, num_workers=2)

valset = torchvision.datasets.ImageFolder(val_path, transform=transform)
valloader = torch.utils.data.DataLoader(valset, batch_size=64, shuffle=False, num_workers=2)

classes = ('dog', 'cat')

# Model
if config.pretrained:

    model_urls = {
        'densenet121': 'https://download.pytorch.org/models/densenet121-a639ec97.pth',
        'densenet169': 'https://download.pytorch.org/models/densenet169-b2777c0a.pth',
        'densenet201': 'https://download.pytorch.org/models/densenet201-c1103571.pth',
        'densenet161': 'https://download.pytorch.org/models/densenet161-8d451a50.pth',
    }
    pretrained_modelname = "densenet121"
    print("Using Pretrained Model: ")
    net = models.__dict__[pretrained_modelname]()
    net.load_state_dict(model_zoo.load_url(model_urls[pretrained_modelname], model_dir="./model_dir/"))
    net.classifier = nn.Linear(1024, 2)
    print("net: ", net)

else:
    if config.resume:
        # Load checkpoint.
        print('==> Resuming from checkpoint..')
        assert os.path.isdir('checkpoint'), 'Error: no checkpoint directory found!'
        checkpoint = torch.load('./checkpoint/ckpt.t7')
        net = checkpoint['net']
        best_acc = checkpoint['acc']
        best_epoch = checkpoint['epoch']
        start_epoch = checkpoint['epoch']
    else:
        print('==> Building model..')
        #net = VGG('VGG19')
        #net = ResNet18()
        #net = GoogLeNet()
        net = DenseNet121()
        #net = ResNeXt29_2x64d()
        #net = LeNet()

if use_cuda:
    net.cuda()
    net = torch.nn.DataParallel(net, device_ids=range(torch.cuda.device_count()))
    cudnn.benchmark = True

criterion = nn.CrossEntropyLoss()
optimizer = optim.SGD(net.parameters(), lr=config.lr, momentum=0.9, weight_decay=5e-4)

# Training
def train(epoch):
    print('\nEpoch: %d' % epoch)
    net.train()
    train_loss = 0
    correct = 0
    total = 0
    for batch_idx, (inputs, targets) in enumerate(trainloader):
        if use_cuda:
            inputs, targets = inputs.cuda(), targets.cuda()
        optimizer.zero_grad()
        inputs, targets = Variable(inputs), Variable(targets)
        outputs = net(inputs)
        loss = criterion(outputs, targets)
        loss.backward()
        optimizer.step()

        train_loss += loss.data[0]
        _, predicted = torch.max(outputs.data, 1)
        total += targets.size(0)
        correct += predicted.eq(targets.data).cpu().sum()

        progress_bar(batch_idx, len(trainloader), 'Loss: %.3f | Acc: %.3f%% (%d/%d)'
            % (train_loss/(batch_idx+1), 100.*correct/total, correct, total))

    print("Epoch: ", epoch, "Acc: ", 100.*correct/total, correct, total)

def val(epoch):

    global best_acc
    global best_epoch

    net.eval()
    val_loss = 0
    correct = 0
    total = 0
    for batch_idx, (inputs, targets) in enumerate(valloader):
        if use_cuda:
            inputs, targets = inputs.cuda(), targets.cuda()
        inputs, targets = Variable(inputs, volatile=True), Variable(targets)
        outputs = net(inputs)
        loss = criterion(outputs, targets)

        val_loss += loss.data[0]
        _, predicted = torch.max(outputs.data, 1)
        total += targets.size(0)
        correct += predicted.eq(targets.data).cpu().sum()

        progress_bar(batch_idx, len(valloader), 'Loss: %.3f | Acc: %.3f%% (%d/%d)'
            % (val_loss/(batch_idx+1), 100.*correct/total, correct, total))

    print("Epoch: ", epoch, "Acc: ", 100.*correct/total, correct, total)
    # Save checkpoint.
    acc = 100. * correct / total
    if acc > best_acc:
        print('Saving..')
        state = {
            #'net': net.module if use_cuda else net,
            'net': net,
            'acc': acc,
            'epoch': epoch,
        }
        if not os.path.isdir('checkpoint'):
            os.mkdir('checkpoint')
        torch.save(state, './checkpoint/ckpt.t7')
        best_acc = acc
        best_epoch = epoch
    print("best epoch: ", best_epoch, " acc: ", best_acc)

for epoch in range(start_epoch, start_epoch + config.epochs):
    if epoch < 20:
        train(epoch)
        val(epoch)
    elif epoch >= 20 and epoch < 40:
        optimizer = optim.SGD(net.parameters(), lr=config.lr/10.0, momentum=0.9, weight_decay=5e-4)
        train(epoch)
        val(epoch)
    else:
        optimizer = optim.SGD(net.parameters(), lr=config.lr/100.0, momentum=0.9, weight_decay=5e-4)
        train(epoch)
        val(epoch)


