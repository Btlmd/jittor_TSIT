import jittor
import jittor.nn as nn
import jittor_utils.misc
from jittor.models import vgg19


from .spectral_norm import spectral_norm
from models.networks.normalization import FADE
# from models.networks.sync_batchnorm import SynchronizedBatchNorm2d
# from infastructure import Module
from icecream import ic


# ResNet block that uses FADE.
# It differs from the ResNet block of SPADE in that
# it takes in the feature map as input, learns the skip connection if necessary.
# This architecture seemed like a standard architecture for unconditional or
# class-conditional GAN architecture using residual block.
# The code was inspired from https://github.com/LMescheder/GAN_stability
# and https://github.com/NVlabs/SPADE.
class FADEResnetBlock(nn.Module):
    def __init__(self, fin, fout, opt):
        super().__init__()
        # attributes
        self.learned_shortcut = (fin != fout)
        fmiddle = fin
        # create conv layers
        self.conv_0 = nn.Conv2d(fin, fmiddle, kernel_size=3, padding=1)
        self.conv_1 = nn.Conv2d(fmiddle, fout, kernel_size=3, padding=1)
        if self.learned_shortcut:
            self.conv_s = nn.Conv2d(fin, fout, kernel_size=1, bias=False)
        # apply spectral norm if specified
        if 'spectral' in opt.norm_G:
            self.conv_0 = spectral_norm(self.conv_0)
            self.conv_1 = spectral_norm(self.conv_1)
            if self.learned_shortcut:
                self.conv_s = spectral_norm(self.conv_s)
        # define normalization layers
        fade_config_str = opt.norm_G.replace('spectral', '')
        self.norm_0 = FADE(fade_config_str, fin, fin)
        self.norm_1 = FADE(fade_config_str, fmiddle, fmiddle)
        if self.learned_shortcut:
            self.norm_s = FADE(fade_config_str, fin, fin)

    # Note the resnet block with FADE also takes in |feat|,
    # the feature map as input
    def execute(self, x, feat):
        x_s = self.shortcut(x, feat)

        dx = self.conv_0(self.actvn(self.norm_0(x, feat)))
        dx = self.conv_1(self.actvn(self.norm_1(dx, feat)))

        out = x_s + dx

        return out

    def shortcut(self, x, feat):
        if self.learned_shortcut:
            x_s = self.conv_s(self.norm_s(x, feat))
        else:
            x_s = x
        return x_s

    def actvn(self, x):
        return nn.leaky_relu(x, 2e-1)


class StreamResnetBlock(nn.Module):
    def __init__(self, fin, fout, opt):
        super().__init__()
        # attributes
        self.learned_shortcut = (fin != fout)
        fmiddle = fin
        # create conv layers
        self.conv_0 = nn.Conv2d(fin, fmiddle, kernel_size=3, padding=1)
        self.conv_1 = nn.Conv2d(fmiddle, fout, kernel_size=3, padding=1)
        if self.learned_shortcut:
            self.conv_s = nn.Conv2d(fin, fout, kernel_size=1, bias=False)
        # apply spectral norm if specified
        if 'spectral' in opt.norm_S:
            self.conv_0 = spectral_norm(self.conv_0)
            self.conv_1 = spectral_norm(self.conv_1)
            if self.learned_shortcut:
                self.conv_s = spectral_norm(self.conv_s)
        # define normalization layers
        subnorm_type = opt.norm_S.replace('spectral', '')
        if subnorm_type == 'batch':
            self.norm_layer_in = nn.BatchNorm2d(fin, affine=True)
            self.norm_layer_out= nn.BatchNorm2d(fout, affine=True)
            if self.learned_shortcut:
                self.norm_layer_s = nn.BatchNorm2d(fout, affine=True)
        elif subnorm_type == 'syncbatch':
            # self.norm_layer_in = nn.BatchNorm2d(fin, affine=True)
            # self.norm_layer_out= nn.BatchNorm2d(fout, affine=True)
            # if self.learned_shortcut:
            #     self.norm_layer_s = nn.BatchNorm2d(fout, affine=True)
            assert False
        elif subnorm_type == 'instance':
            self.norm_layer_in = nn.InstanceNorm2d(fin, affine=False)
            self.norm_layer_out= nn.InstanceNorm2d(fout, affine=False)
            if self.learned_shortcut:
                self.norm_layer_s = nn.InstanceNorm2d(fout, affine=False)
        else:
            raise ValueError('normalization layer %s is not recognized' % subnorm_type)

    def execute(self, x):
        # IPython.embed()

        # import IPython
        # IPython.embed(header="jittor res block")
        
        x_s = self.shortcut(x)
        

        dx = self.actvn(self.norm_layer_in(self.conv_0(x)))
        dx = self.actvn(self.norm_layer_out(self.conv_1(dx)))
        out = x_s + dx
        return out

    def shortcut(self,x):
        if self.learned_shortcut:
            x_s = self.actvn(self.norm_layer_s(self.conv_s(x)))
        else:
            x_s = x
        return x_s

    def actvn(self, x):
        return nn.leaky_relu(x, 2e-1)


# ResNet block used in pix2pixHD
# We keep the same architecture as pix2pixHD.
class ResnetBlock(nn.Module):
    def __init__(self, dim, norm_layer, activation=nn.ReLU(False), kernel_size=3):
        super().__init__()

        pw = (kernel_size - 1) // 2
        self.conv_block = nn.Sequential(
            nn.ReflectionPad2d(pw),
            norm_layer(nn.Conv2d(dim, dim, kernel_size=kernel_size)),
            activation,
            nn.ReflectionPad2d(pw),
            norm_layer(nn.Conv2d(dim, dim, kernel_size=kernel_size))
        )

    def execute(self, x):
        y = self.conv_block(x)
        out = x + y
        return out


# VGG architecture, used for the perceptual loss using a pretrained VGG network
class VGG19(nn.Module):
    def __init__(self, requires_grad=False):
        super().__init__()
        vgg_pretrained_features = vgg19(pretrained=True).features
        self.slice1 = nn.Sequential()
        self.slice2 = nn.Sequential()
        self.slice3 = nn.Sequential()
        self.slice4 = nn.Sequential()
        self.slice5 = nn.Sequential()
        for x in range(2):
            self.slice1.add_module(str(x), vgg_pretrained_features[x])
        for x in range(2, 7):
            self.slice2.add_module(str(x), vgg_pretrained_features[x])
        for x in range(7, 12):
            self.slice3.add_module(str(x), vgg_pretrained_features[x])
        for x in range(12, 21):
            self.slice4.add_module(str(x), vgg_pretrained_features[x])
        for x in range(21, 30):
            self.slice5.add_module(str(x), vgg_pretrained_features[x])
        if not requires_grad:
            for param in self.parameters():
                param.requires_grad = False

    def execute(self, X):
        h_relu1 = self.slice1(X)
        h_relu2 = self.slice2(h_relu1)
        h_relu3 = self.slice3(h_relu2)
        h_relu4 = self.slice4(h_relu3)
        h_relu5 = self.slice5(h_relu4)
        out = [h_relu1, h_relu2, h_relu3, h_relu4, h_relu5]
        return out
