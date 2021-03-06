import os
import torch
import numpy as np
import torch.nn as nn

import torch
import torchvision
import torchvision.transforms as transforms

from flask import Flask
from PIL import Image, ImageDraw
from flask import request
from flask import render_template
from torch.nn import functional as F
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from torchvision.models.detection import  FasterRCNN
from torchvision.models.detection.rpn import AnchorGenerator


app = Flask(__name__)
UPLOAD_FOLDER = "api_image_store"
DEVICE = "cpu"

def model():
    # load the COCO pre-trained model
    # we will keep the image size to 1024 pixels instead of the original 800,
    # this will ensure better training and testing results, although it may...
    # ... increase the training time (a tarde-off)
    model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=True, 
                                                                 min_size=1024)
    # one class is pneumonia, and the other is background
    num_classes = 2
    # get the input features for the classifier
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    # replace pre-trained head with our features head
    # the head layer will classify the images based on our data input features
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)

    return model

def format_prediction_string(boxes, scores):
    pred_strings = []
    for j in zip(scores, boxes):
        pred_strings.append("Confidence: {0:.4f}, Coordinates: {1} {2} {3} {4}".format(j[0]*100, j[1][0], j[1][1], j[1][2], j[1][3]))

    return " ".join(pred_strings)

def predict(image_path, model):
    # define the torchvision image transforms
    transform = transforms.Compose([
        transforms.ToTensor(),
    ])
    results = []
    detection_threshold = 0.9
    model.eval()
    with torch.no_grad():
        test_images = image_path
        orig_image = Image.open(test_images)
        orig_image = orig_image.convert('RGB')
        image = orig_image.copy()
        image = transform(image).to(DEVICE)
        image = torch.unsqueeze(image, 0)

        cpu_device = torch.device("cpu")

        outputs = model(image)
        
        outputs = [{k: v.to(cpu_device) for k, v in t.items()} for t in outputs]
        if len(outputs[0]['boxes']) != 0:
            for counter in range(len(outputs[0]['boxes'])):
                boxes = outputs[0]['boxes'].data.cpu().numpy()
                scores = outputs[0]['scores'].data.cpu().numpy()
                boxes = boxes[scores >= detection_threshold].astype(np.int32)
                draw_boxes = boxes.copy()
                boxes[:, 2] = boxes[:, 2] - boxes[:, 0]
                boxes[:, 3] = boxes[:, 3] - boxes[:, 1]
                
            for box in draw_boxes:
                draw = ImageDraw.Draw(orig_image)   
                draw.rectangle([(box[0], box[1]), (box[2], box[3])], outline ="red") 
                draw.rectangle([(box[0]+1, box[1]+1), (box[2]+1, box[3]+1)], outline ="red") 
        
            print('PATH.......', image_path)
            orig_image.save(f"static/prediction/{image_path.split(os.path.sep)[-1]}")
                    
            result = {
                'Prediction': format_prediction_string(boxes, scores)
            }
            results.append(result)
        else:
            result = {
                'Prediction': None
            }
            results.append(result)

    print(results[0]['Prediction'])
    if results[0]['Prediction'] == None or results[0]['Prediction'] == '':
        return 'No pneumonia found. Patient is healthy.', False
    else:
        return results[0]['Prediction'], True


@app.route("/", methods=["GET", "POST"])
def upload_predict():
    if request.method == "POST":
        image_file = request.files["image"]
        if image_file:
            image_location = os.path.join(
                UPLOAD_FOLDER,
                image_file.filename
            )
            image_file.save(image_location)
            pred, show_image = predict(image_location, MODEL)
            return render_template("index.html", prediction=pred, show_image=show_image, name=image_file.filename)
    return render_template("index.html", prediction=0, image_loc=None)


if __name__ == "__main__":
    MODEL = model()
    MODEL.load_state_dict(torch.load("fasterrcnn_resnet50_fpn.pth", map_location=torch.device(DEVICE)))
    MODEL.to(DEVICE)
    # app.run(host="127.0.0.1", port=12000, debug=True) # ucomment this when running on local machine
    app.run(debug=True)