import pytorch_lightning as pl
import segmentation_models_pytorch as smp
import torch
import torch.nn as nn
import wandb
from torch.optim import Adam
from torch.optim.lr_scheduler import StepLR
from torchmetrics import F1Score, JaccardIndex, Precision, Recall


class smp_model_v2(nn.Module):
    def __init__(self, in_channels, out_channels, model_type, num_classes, encoder_weights):
        super(smp_model_v2, self).__init__()

        # Use MobileNetV2 pre-trained model as encoder
        self.model = smp.Unet(
            encoder_name="mobilenet_v2",
            encoder_weights=encoder_weights,
            in_channels=in_channels,  # The number of input channels, which is 14
            classes=num_classes,  # Output classes, which is 1
        )

    def forward(self, x):
        return self.model(x)


class LandslideModel(pl.LightningModule):
    def __init__(self, config, alpha=0.5):
        super(LandslideModel, self).__init__()

        model_type = config["model_config"]["model_type"]
        in_channels = config["model_config"]["in_channels"]
        num_classes = config["model_config"]["num_classes"]
        self.alpha = alpha  # Assign the alpha value to the class variable
        self.lr = config["train_config"]["lr"]

        if model_type == "unet":
            self.model = UNet(in_channels=in_channels, out_channels=num_classes)
        else:
            encoder_weights = config["model_config"]["encoder_weights"]
            # Use the custom smp_model_v2 instead of smp_model
            self.model = smp_model_v2(
                in_channels=in_channels,
                out_channels=num_classes,
                model_type=model_type,
                num_classes=num_classes,
                encoder_weights=encoder_weights,
            )

        self.weights = torch.tensor([5], dtype=torch.float32).to(self.device)
        self.wce = nn.BCELoss(weight=self.weights)

        self.train_f1 = F1Score(task="binary")
        self.val_f1 = F1Score(task="binary")

        self.train_precision = Precision(task="binary")
        self.val_precision = Precision(task="binary")

        self.train_recall = Recall(task="binary")
        self.val_recall = Recall(task="binary")

        self.train_iou = JaccardIndex(task="binary")
        self.val_iou = JaccardIndex(task="binary")

    def forward(self, x):
        return self.model(x)

    def training_step(self, batch, batch_idx):
        x, y = batch
        y_hat = torch.sigmoid(self(x))

        wce_loss = self.wce(y_hat, y)
        dice = dice_loss(y_hat, y)

        combined_loss = (1 - self.alpha) * wce_loss + self.alpha * dice

        precision = self.train_precision(y_hat, y)
        recall = self.train_recall(y_hat, y)
        iou = self.train_iou(y_hat, y)
        loss_f1 = self.train_f1(y_hat, y)

        self.log("train_precision", precision)
        self.log("train_recall", recall)
        self.log("train_wce", wce_loss)
        self.log("train_dice", dice)
        self.log("train_iou", iou)
        self.log("train_f1", loss_f1)
        self.log("train_loss", combined_loss)
        return {"loss": combined_loss}

    def validation_step(self, batch, batch_idx):
        x, y = batch
        y_hat = torch.sigmoid(self(x))

        wce_loss = self.wce(y_hat, y)
        dice = dice_loss(y_hat, y)

        combined_loss = (1 - self.alpha) * wce_loss + self.alpha * dice

        precision = self.val_precision(y_hat, y)
        recall = self.val_recall(y_hat, y)
        iou = self.val_iou(y_hat, y)
        loss_f1 = self.val_f1(y_hat, y)

        self.log("val_precision", precision)
        self.log("val_recall", recall)
        self.log("val_wce", wce_loss)
        self.log("val_dice", dice)
        self.log("val_iou", iou)
        self.log("val_f1", loss_f1)
        self.log("val_loss", combined_loss)

        if self.current_epoch % 10 == 0:
            x = (x - x.min()) / (x.max() - x.min())
            x = x[:, 0:3]
            x = x.permute(0, 2, 3, 1)
            y_hat = (y_hat > 0.5).float()

            class_labels = {0: "no landslide", 1: "landslide"}  # Define class_labels here

            self.logger.experiment.log(
                {
                    "image": wandb.Image(
                        x[0].cpu().detach().numpy(),
                        masks={
                            "predictions": {
                                "mask_data": y_hat[0][0].cpu().detach().numpy(),
                                "class_labels": class_labels,
                            },
                            "ground_truth": {
                                "mask_data": y[0][0].cpu().detach().numpy(),
                                "class_labels": class_labels,
                            },
                        },
                    )
                }
            )
        return {"val_loss": combined_loss}

    def configure_optimizers(self):
        optimizer = Adam(self.parameters(), lr=self.lr)
        scheduler = StepLR(optimizer, step_size=30, gamma=0.1)
        return [optimizer], [scheduler]


class Block(nn.Module):
    def __init__(self, inputs=3, middles=64, outs=64):
        super().__init__()

        self.conv1 = nn.Conv2d(inputs, middles, 3, 1, 1)
        self.conv2 = nn.Conv2d(middles, outs, 3, 1, 1)
        self.relu = nn.ReLU()
        self.bn = nn.BatchNorm2d(outs)
        self.pool = nn.MaxPool2d(2, 2)

    def forward(self, x):
        x = self.relu(self.conv1(x))
        x = self.relu(self.bn(self.conv2(x)))
        return self.pool(x), x


class UNet(nn.Module):
    def __init__(self, in_channels=3, out_channels=1):
        super().__init__()

        self.en1 = Block(in_channels, 64, 64)
        self.en2 = Block(64, 128, 128)
        self.en3 = Block(128, 256, 256)
        self.en4 = Block(256, 512, 512)
        self.en5 = Block(512, 1024, 512)

        self.upsample4 = nn.ConvTranspose2d(512, 512, 2, stride=2)
        self.de4 = Block(1024, 512, 256)

        self.upsample3 = nn.ConvTranspose2d(256, 256, 2, stride=2)
        self.de3 = Block(512, 256, 128)

        self.upsample2 = nn.ConvTranspose2d(128, 128, 2, stride=2)
        self.de2 = Block(256, 128, 64)

        self.upsample1 = nn.ConvTranspose2d(64, 64, 2, stride=2)
        self.de1 = Block(128, 64, 64)

        self.conv_last = nn.Conv2d(64, out_channels, kernel_size=1, stride=1, padding=0)

    def forward(self, x):
        x, e1 = self.en1(x)
        x, e2 = self.en2(x)
        x, e3 = self.en3(x)
        x, e4 = self.en4(x)
        _, x = self.en5(x)

        x = self.upsample4(x)
        x = torch.cat([x, e4], dim=1)
        _, x = self.de4(x)

        x = self.upsample3(x)
        x = torch.cat([x, e3], dim=1)
        _, x = self.de3(x)

        x = self.upsample2(x)
        x = torch.cat([x, e2], dim=1)
        _, x = self.de2(x)

        x = self.upsample1(x)
        x = torch.cat([x, e1], dim=1)
        _, x = self.de1(x)

        x = self.conv_last(x)

        return x


def dice_loss(y_hat, y):
    smooth = 1e-6
    y_hat = y_hat.view(-1)
    y = y.view(-1)
    intersection = (y_hat * y).sum()
    union = y_hat.sum() + y.sum()
    dice = (2 * intersection + smooth) / (union + smooth)
    return 1 - dice
