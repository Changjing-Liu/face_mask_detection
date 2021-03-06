#!/usr/bin/env python
# coding: utf-8

# # Face mask detection (Faster R-CNN) (Pytorch)
# - Simple fine-tuning with Faster R-CNN

# import all the tools we need
import sys
import urllib
import pandas as pd
import numpy as np
import cv2
import matplotlib.pyplot as plt
import torch
import torchvision
import torchvision.transforms as transforms
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from torch.utils.data import DataLoader, Dataset
from sklearn.model_selection import train_test_split
import matplotlib.patches as patches
import os
from PIL import Image
import random
import xml.etree.ElementTree as ET
import time
import requests
sys.path.append("utils")
from utils.mean_avg_precision import mean_average_precision

# In[2]:


# ### Create 2 helper functions
# 1. one for read the data from xml file
# 2. the second function is used for drawing bounding boxes.

# In[3]:
def get_device():
    ''' Get device (if GPU is available, use GPU) '''
    return 'cuda' if torch.cuda.is_available() else 'cpu'


# Helper function for read the data (label and bounding boxes) from xml file 
def read_annot(file_name, xml_dir):
    """
    Function used to get the bounding boxes and labels from the xml file
    Input:
        file_name: image file name
        xml_dir: directory of xml file
    Return:
        bbox : list of bounding boxes
        labels: list of labels
    """
    bbox = []
    labels = []

    annot_path = os.path.join(xml_dir, file_name[:-3] + 'xml')
    tree = ET.parse(annot_path)
    root = tree.getroot()
    for boxes in root.iter('object'):
        ymin = int(boxes.find("bndbox/ymin").text)
        xmin = int(boxes.find("bndbox/xmin").text)
        ymax = int(boxes.find("bndbox/ymax").text)
        xmax = int(boxes.find("bndbox/xmax").text)
        label = boxes.find('name').text
        bbox.append([xmin, ymin, xmax, ymax])
        if label == 'with_mask':
            label_idx = 2
        else:
            label_idx = 1
        labels.append(label_idx)

    return bbox, labels


# help function for drawing bounding boxes on image
def draw_boxes(img, boxes, labels, thickness=1):
    """
    Function to draw bounding boxes
    Input:
        img: array of img (h, w ,c)
        boxes: list of boxes (int)
        labels: list of labels (int)
    
    """
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    for box, label in zip(boxes, labels):
        box = [int(x) for x in box]
        if label == 2:
            color = (0, 225, 0)  # green
        elif label == 1:
            color = (0, 0, 225)  # red
        cv2.rectangle(img, (box[0], box[1]), (box[2], box[3]), color, thickness)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


class image_dataset(Dataset):
    def __init__(self, image_list, image_dir, xml_dir):
        self.image_list = image_list
        self.image_dir = image_dir
        self.xml_dir = xml_dir

    def __getitem__(self, idx):
        """
        Load the image
        """
        img_name = self.image_list[idx]
        img_path = os.path.join(self.image_dir, img_name)
        img = Image.open(img_path).convert('RGB')
        img = transforms.ToTensor()(img)
        """
        build the target dict
        """
        bbox, labels = read_annot(img_name, self.xml_dir)
        boxes = torch.as_tensor(bbox, dtype=torch.float32)
        labels = torch.as_tensor(labels, dtype=torch.int64)

        area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
        area = torch.as_tensor(area, dtype=torch.float32)
        iscrowd = torch.zeros((len(bbox),), dtype=torch.int64)

        target = {}

        target['boxes'] = boxes
        target['labels'] = labels
        target['image_id'] = torch.tensor([idx])
        target['area'] = area
        target['iscrowed'] = iscrowd
        return img, target

    def __len__(self):
        return len(self.image_list)


# - Get the data loader

# In[6]:


def collate_fn(batch):
    return tuple(zip(*batch))


def prep_dataloader(mask_dataset, xml_path, mode, batch_size, n_jobs):
    mask_loader = DataLoader(mask_dataset,
                             batch_size=batch_size,
                             shuffle=(mode == 'train'),
                             num_workers=n_jobs,
                             collate_fn=collate_fn)
    return mask_loader


# Setting up the model
def Faster_RCNN():
    num_classes = 3  # background, without_mask, with_mask

    model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=True)
    # model = torchvision.models.detection.fasterrcnn_mobilenet_v3_large_fpn(pretrained=True)
    # pre = torch.load('checkpoint/fasterrcnn_resnet50_fpn_coco-258fb6c6.pth')
    # model.load_state_dict(pre)
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)

    model = model.to(device)
    return model

# training
def train(tr_set, dev_set, model, config, device):
    num_epochs = config['num_epochs']

    # setup optimizer
    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.SGD(params, config['lr'], config['momentum'], config['weight_decay'])

    # Main training function
    loss_list = []
    tr_list = []
    dev_list = []
    early_stop_cnt = 0
    min_mse = 1000
    max_ap = 0
    cnt_epoch = 0
    for epoch in range(num_epochs):
        cnt_epoch = epoch + 1
        print('Starting training....{}/{}'.format(epoch + 1, num_epochs))
        loss_sub_list = []
        start = time.time()
        model.train()
        i = 0
        epoch_loss = 0
        for images, targets in tr_set:
            i += 1
            images = list(image.to(device) for image in images)
            targets = [{k: v.to(device) for k, v in t.items()} for t in targets]

            loss_dict = model(images, targets)
            losses = sum(loss for loss in loss_dict.values())
            loss_value = losses.item()
            loss_sub_list.append(loss_value)

            # update optimizer and learning rate
            optimizer.zero_grad()
            losses.backward()
            optimizer.step()
            # lr_scheduler.step()
        end = time.time()

        epoch_loss = np.mean(loss_sub_list)
        loss_list.append(epoch_loss)

        # After each epoch, test your model on the validation (development) set.
        dev_ap = get_map(dev_set)
        tr_ap = get_map(tr_set)
        dev_list.append(dev_ap)
        tr_list.append(tr_ap)
        if(dev_ap<tr_ap):
            min_mse = epoch_loss
            torch.save(model.state_dict(), 'checkpoint/model.pth')
            print('Epoch loss: {:.3f} , time used: ({:.1f}s)'.format(min_mse, end - start))
            early_stop_cnt = 0
        else:
            early_stop_cnt += 1
        if early_stop_cnt > config['early_stop']:
            # Stop training if your model stops improving for "config['early_stop']" epochs.
            break

    x = np.arange(len(loss_list))
    plt.plot(loss_list, 'r', label='training loss')
    # plt.plot(dev_list, 'b', label='validation loss')
    plt.title('Loss Curve')
    plt.legend(loc="lower left")
    plt.xlim(1, len(loss_list))
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.savefig("output/loss.png")

    plt.cla()
    plt.plot(dev_list, 'r', label='validation loss')
    plt.plot(tr_list, 'g', label='training loss')
    plt.title('Accuracy Curve')
    plt.legend(loc="lower left")
    plt.xlim(1, len(loss_list))
    plt.xlabel('Epoch')
    plt.ylabel('mAP')
    plt.savefig("output/Accuracy.png")

# validation
def dev(dv_set, model, device):
    model.eval()                                # set model to evalutation mode
    total_loss = 0
    loss_sub_list = []
    for imgs, annotations in dv_set:  # iterate through the dataloader
        imgs = list(img.to(device) for img in imgs)
        annotations = [{k: v.to(device) for k, v in t.items()} for t in annotations]
        # x, y = x.to(device), y.to(device)       # move data to device (cpu/cuda)
        with torch.no_grad():  # disable gradient calculation
            # pred = model(imgs)                     # forward pass (compute output)
            mse_loss = model(imgs, annotations)  # compute loss
        # total_loss += mse_loss.detach().cpu().item() * len(imgs)  # accumulate loss
        total_loss = sum(loss for loss in mse_loss.values())
        loss_value = total_loss.item()
        loss_sub_list.append(loss_value)
    total_loss = np.mean(loss_sub_list)  # compute averaged loss

    return total_loss


# # Prediction

# helper function for single image prediction
def single_img_predict(img, model, nm_thrs=0.3, score_thrs=0.8):
    test_img = transforms.ToTensor()(img)
    model.eval()

    with torch.no_grad():
        predictions = model(test_img.unsqueeze(0).to(device))

    test_img = test_img.permute(1, 2, 0).numpy()

    # non-max supression
    keep_boxes = torchvision.ops.nms(predictions[0]['boxes'].cpu(), predictions[0]['scores'].cpu(), nm_thrs)

    # Only display the bounding boxes which higher than the threshold
    score_filter = predictions[0]['scores'].cpu().numpy()[keep_boxes] > score_thrs

    # get the filtered result
    test_boxes = predictions[0]['boxes'].cpu().numpy()[keep_boxes][score_filter]
    test_labels = predictions[0]['labels'].cpu().numpy()[keep_boxes][score_filter]

    return test_img, test_boxes, test_labels


def plot_img(img, predict, annotation):
    fig, ax = plt.subplots(1, 2)
    img = img.cpu().data

    ax[0].imshow(img.permute(1, 2, 0))  # rgb, w, h => w, h, rgb
    ax[1].imshow(img.permute(1, 2, 0))
    ax[0].set_title("real")
    ax[1].set_title("predict")

    for box in annotation["boxes"]:
        xmin, ymin, xmax, ymax = box
        rect = patches.Rectangle((xmin, ymin), (xmax - xmin), (ymax - ymin), linewidth=1, edgecolor='r',
                                 facecolor='none')
        ax[0].add_patch(rect)

    for box in predict["boxes"]:
        xmin, ymin, xmax, ymax = box
        rect = patches.Rectangle((xmin, ymin), (xmax - xmin), (ymax - ymin), linewidth=1, edgecolor='r',
                                 facecolor='none')
        ax[1].add_patch(rect)

    # plt.savefig()
    # plt.show()

def get_map(set):
    model.eval()
    with torch.no_grad():
        a = 0
        for imgs, annotations in set:
            imgs = list(img.to(device) for img in imgs)
            annotations = [{k: v.to(device) for k, v in t.items()} for t in annotations]
            preds = model(imgs)
            annotation=annotations[0]
            predict=preds[0]
            true_boxes=[]
            pred_bboxes=[]
            anno_boxs = annotation["boxes"]
            anno_labels = annotation["labels"]
            for i in range(len(anno_boxs)):
                xmin, ymin, xmax, ymax = anno_boxs[i]
                l_true =[a, anno_labels[i], 1,xmin, ymin, xmax, ymax]
                true_boxes.append(l_true)

            pre_boxs = predict["boxes"]
            pre_labels = predict["labels"]
            pre_scores = predict["scores"]
            for i in range(len(pre_boxs)):
                xmin, ymin, xmax, ymax = pre_boxs[i]
                l_pre = [a, pre_labels[i], pre_scores[i], xmin, ymin, xmax, ymax]
                pred_bboxes.append(l_pre)
            a + 1
    precisions,recalls,ap = mean_average_precision(pred_bboxes, true_boxes, iou_threshold=0.5,box_format="corners", num_classes=3)
    return ap
def test(tt_set):
    pred_bboxes = []
    true_boxes = []
    with torch.no_grad():
        a = 0
        for imgs, annotations in tt_set:
            imgs = list(img.to(device) for img in imgs)
            annotations = [{k: v.to(device) for k, v in t.items()} for t in annotations]
            preds = model(imgs)
            annotation = annotations[0]
            predict = preds[0]

            anno_boxs = annotation["boxes"]
            anno_labels = annotation["labels"]
            for i in range(len(anno_boxs)):
                xmin, ymin, xmax, ymax = anno_boxs[i]
                l_true = [a, anno_labels[i], 1, xmin, ymin, xmax, ymax]
                true_boxes.append(l_true)

            pre_boxs = predict["boxes"]
            pre_labels = predict["labels"]
            pre_scores = predict["scores"]
            for i in range(len(pre_boxs)):
                xmin, ymin, xmax, ymax = pre_boxs[i]
                l_pre = [a, pre_labels[i], pre_scores[i], xmin, ymin, xmax, ymax]
                pred_bboxes.append(l_pre)
            a + 1
    precisions, recalls, ap = mean_average_precision(pred_bboxes, true_boxes, iou_threshold=0.5, box_format="corners",
                                                     num_classes=3)
    plt.plot(recalls, precisions, 'b', label='ap=%f' % ap)
    plt.title('precision-recall curve')
    plt.legend(loc="lower left")
    plt.xlim(-0.1, 1.1)
    plt.xlabel('Recall')
    plt.ylabel('Precision')
    plt.savefig("output/ap.png")

if __name__ == '__main__':
    device = get_device()
    print(device)
    config = {
        'num_epochs': 30,  # maximum number of epochs
        'batch_size': 1,  # mini-batch size for dataloader
        'n_jobs': 2,
        'optimizer': 'SGD',  # optimization algorithm (optimizer in torch.optim)
        # 'optim_hparas': {  # hyper-parameters for the optimizer (depends on which optimizer you are using)
        'lr': 0.001,  # learning rate of SGD
        'momentum': 0.9,  # momentum for SGD
        'weight_decay': 0.0005,
        # },
        'early_stop': 5,  # early stopping epochs (the number epochs since your model's last improvement)
        'dir_path': './data_set/face_mask_detection/IMAGES',
        'xml_path': './data_set/face_mask_detection/ANNOTATIONS',
        'save_path': 'models/model.pth'  # your model will be saved here
    }
    file_list = os.listdir(config['dir_path'])
    # How many image files?
    print('There are total {} images.'.format(len(file_list)))
    full_dataset = image_dataset(file_list, config['dir_path'], config['xml_path'])

    train_size = int(0.6 * len(full_dataset))  # 0.6
    valid_size = int(0.2 * len(full_dataset))  # 0.2
    test_size = len(full_dataset) - train_size - valid_size  # 0.2
    train_set, valid_set, test_set = torch.utils.data.random_split(full_dataset, [train_size, valid_size,test_size])
    np.save('checkpoint/train_set.npy', train_set)
    np.save('checkpoint/test_set.npy', test_set)
    # print(type(train_set))
    # train1_set = np.load("checkpoint/train_set.npy")
    # test1_set = np.load("checkpoint/test_set.npy")

    tr_set = prep_dataloader(train_set, config['xml_path'], 'train', config['batch_size'], config['n_jobs'])
    dv_set = prep_dataloader(valid_set, config['xml_path'], 'train', config['batch_size'], config['n_jobs'])
    tt_set = prep_dataloader(test_set, config['xml_path'], 'test', config['batch_size'], config['n_jobs'])
    model = Faster_RCNN()
    train(tr_set, dv_set, model, config, device)
    test(tt_set)