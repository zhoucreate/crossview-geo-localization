# train spade net
#python train.py \
#--name='three_view_long_share_d0.5_256_s1_google_lr0.005_spade_v24.11_210ep_weather_0110000_alpha1' \
#--experiment_name='three_view_long_share_d0.5_256_s1_google_lr0.005_spade_v24.11_210ep_weather_0110000_alpha1' \
#--data_dir='/home/wangtingyu/datasets/University-Release/train' \
#--views=3 \
#--droprate=0.5 \
#--extra \
#--share \
#--stride=1 \
#--h=256 \
#--w=256 \
#--lr=0.005 \
#--gpu_ids='2' \
#--norm='spade' \
#--iaa \
#--multi_weather \
#--btnk 0 1 1 0 0 0 0 \
#--conv_norm='none' \
#--alpha=1 \
#--adain='a'
#
#python test_iaa.py \
#--name='three_view_long_share_d0.5_256_s1_google_lr0.005_spade_v24.11_210ep_weather_0110000_alpha1' \
#--test_dir='/home/wangtingyu/datasets/University-Release/test' \
#--iaa \
#--gpu_ids='2'

 python train.py \
 --name='three_view_long_share_d0.75_256_lr0.0025_210ep_weather_ConvNext_22k_LPN_block8_s1_onebyone_centerloss0.75_color' \
 --experiment_name='three_view_long_share_d0.75_256_lr0.0025_210ep_weather_ConvNext_22k_LPN_block8_s1_onebyone_centerloss0.75_color' \
 --data_dir='/data0/zhoujiayu/dataset/University-Release/train' \
 --views=3 \
 --droprate=0.75 \
 --share \
 --stride=1 \
 --h=256 \
 --w=256 \
 --lr=0.0025 \
 --gpu_ids='3' \
 --norm='convenxt' \
 --erasing_p=0.4 \
 --color_jitter \
 --block=8 \
 --LPN \
 --iaa \
 --multi_weather \
 --btnk 1 0 0 0 0 0 0 \
 --conv_norm='none' \
 --adain='a'

# python test_iaa.py \
# --name='three_view_long_share_d0.75_256_lr0.0025_210ep_weather_ConvNext_22k_LPN_block8_s1_onebyone_centerloss0.75' \
# --test_dir='/data0/zhoujiayu/dataset/University-Release/test' \
# --iaa  \
# --gpu_ids='3'

# python test_160wx.py \
# --name='three_view_long_share_d0.5_256_lr0.0025_210ep_weather_ConvNext_22k_LPN_block8_s1_onebyone_TripletAttention' \
# --test_dir='/data0/zhoujiayu/dataset/University-Release/test' \
# --gpu_ids='2'

# python test_160k.py \
# --name='three_view_long_share_d0.75_256_lr0.0025_210ep_weather_ConvNext_22k_LPN_block8_s1_onebyone_1429' \
# --test_dir='/data0/zhoujiayu/dataset/University-Release/test' \
# --gpu_ids='3'

#traing dense_lpn_gem.py
# python train.py \
# --name='two_view_share_d0.5_512_lr0.01_convnext_tri_MCCG' \
# --experiment_name='two_view_share_d0.5_512_lr0.01_convnext_tri_MCCG' \
# --data_dir='/data0/zhoujiayu/dataset/University-Release/train' \
# --views=2 \
# --droprate=0.5 \
# --share \
# --stride=1 \
# --h=512 \
# --w=512 \
# --lr=0.01 \
# --gpu_ids='3' \
# --norm='convnext' \
# --block=4 \
# --dense_LPN \
# --iaa \
# --multi_weather \
# --btnk 1 0 0 0 0 0 0 \
# --conv_norm='none' \
# --adain='a'

# python test_160wx.py \
# --name='two_view_share_d0.5_512_lr0.001_convnext_gem_denseLPN_2' \
# --test_dir='/data0/zhoujiayu/dataset/University-Release/test' \
# --gpu_ids='3'

# python test_convnext.py \


#  python test_iaa.py \
# --name='two_view_share_d0.5_512_lr0.001_convnext_tri_MCCG' \
# --test_dir='/data0/zhoujiayu/dataset/University-Release/test' \
# --gpu_ids='3'

# training ibn net
# python train.py \
# --name='three_view_long_share_d0.5_256_s1_google_lr0.005_ibn_v24.11_210ep_weather' \
# --experiment_name='three_view_long_share_d0.5_256_s1_google_lr0.005_ibn_v24.11_210ep_weather' \
# --data_dir='/data0/zhoujiayu/dataset/University-Release/train' \
# --views=3 \
# --droprate=0.5 \
# --extra \
# --share \
# --stride=1 \
# --h=256 \
# --w=256 \
# --lr=0.005 \
# --gpu_ids='3' \
# --norm='ibn' \
# --iaa \
# --multi_weather \
# --btnk 1 0 0 0 0 0 0 \
# --conv_norm='none' \
# --adain='a'

# python test_iaa.py \
# --name='three_view_long_share_d0.5_256_s1_google_lr0.005_ibn_v24.11_210ep_weather' \
# --test_dir='/home/wangtingyu/datasets/University-Release/test' \
# --iaa \
# --gpu_ids='4'

# training ibn net
#python train.py \
#--name='three_view_long_share_d0.75_256_s1_google_lr0.005_ibn_v21.9_210ep_weather_r6' \
#--experiment_name='three_view_long_share_d0.75_256_s1_google_lr0.005_ibn_v21.9_210ep_weather_r6' \
#--data_dir='/home/wangtyu/datasets/University-Release/train' \
#--views=3 \
#--droprate=0.75 \
#--extra \
#--share \
#--stride=1 \
#--h=256 \
#--w=256 \
#--lr=0.005 \
#--gpu_ids='2' \
#--norm='ibn' \
#--iaa \
#--multi_weather \
#--adain='a'
#
#python test_iaa.py \
#--name='three_view_long_share_d0.75_256_s1_google_lr0.005_ibn_v21.9_210ep_weather_r6' \
#--test_dir='/home/wangtyu/datasets/University-Release/test' \
#--iaa \
#--gpu_ids='2'

# train original university1652 ada-ibn
#python train.py \
#--name='three_view_long_share_d0.75_256_s1_google_lr0.005_ada-ibn_v21.9_210ep_no-style-loss' \
#--experiment_name='three_view_long_share_d0.75_256_s1_google_lr0.005_ada-ibn_v21.9_210ep_no-style-loss' \
#--data_dir='/home/wangtyu/datasets/University-Release/train' \
#--views=3 \
#--droprate=0.75 \
#--extra \
#--share \
#--stride=1 \
#--h=256 \
#--w=256 \
#--lr=0.005 \
#--gpu_ids='2' \
#--norm='ada-ibn' \
#--iaa \
#--adain='a'
#
#python test_iaa.py \
#--name='three_view_long_share_d0.75_256_s1_google_lr0.005_ada-ibn_v21.9_210ep_no-style-loss' \
#--test_dir='/home/wangtyu/datasets/University-Release/test' \
#--iaa \
#--gpu_ids='2'

# train original university1652 ibn
#python train.py \
#--name='three_view_long_share_d0.75_256_s1_google_lr0.005_ibn_v21.9_210ep' \
#--experiment_name='three_view_long_share_d0.75_256_s1_google_lr0.005_ibn_v21.9_210ep' \
#--data_dir='/home/wangtyu/datasets/University-Release/train' \
#--views=3 \
#--droprate=0.75 \
#--extra \
#--share \
#--stride=1 \
#--h=256 \
#--w=256 \
#--lr=0.005 \
#--gpu_ids='1' \
#--norm='ibn' \
#--iaa \
#--adain='a'
#
#python test_iaa.py \
#--name='three_view_long_share_d0.75_256_s1_google_lr0.005_ibn_v21.9_210ep' \
#--test_dir='/home/wangtyu/datasets/University-Release/test' \
#--iaa \
#--gpu_ids='1'

# train LPN weather
# python train.py \
# --name='three_view_long_share_d0.5_256_s1_google_lr0.001_LPN_v24.11_210ep_weather' \
# --experiment_name='three_view_long_share_d0.5_256_s1_google_lr0.001_LPN_v24.11_210ep_weather' \
# --data_dir='/home/wangtingyu/datasets/University-Release/train' \
# --views=3 \
# --droprate=0.5 \
# --extra \
# --share \
# --stride=1 \
# --h=256 \
# --w=256 \
# --lr=0.001 \
# --gpu_ids='5' \
# --LPN \
# --iaa \
# --multi_weather \
# --block=4 \
# --conv_norm='none' \
# --adain='a'

# python test_iaa.py \
# --name='three_view_long_share_d0.5_256_s1_google_lr0.001_LPN_v24.11_210ep_weather' \
# --test_dir='/home/wangtingyu/datasets/University-Release/test' \
# --iaa \
# --gpu_ids='5'

# LPN + Spade
# python train.py \
# --name='three_view_long_share_d0.5_256_s1_google_lr0.001_LPN_Spade_v24.11_210ep_weather' \
# --experiment_name='three_view_long_share_d0.5_256_s1_google_lr0.001_LPN_Spade_v24.11_210ep_weather' \
# --data_dir='/home/wangtingyu/datasets/University-Release/train' \
# --views=3 \
# --droprate=0.5 \
# --extra \
# --share \
# --stride=1 \
# --h=256 \
# --w=256 \
# --lr=0.001 \
# --gpu_ids='0' \
# --LPN \
# --iaa \
# --multi_weather \
# --btnk 0 1 1 0 0 0 0 \
# --norm='spade' \
# --block=4 \
# --conv_norm='none' \
# --adain='a'

# python test_iaa.py \
# --name='three_view_long_share_d0.5_256_s1_google_lr0.001_LPN_Spade_v24.11_210ep_weather' \
# --test_dir='/home/wangtingyu/datasets/University-Release/test' \
# --iaa \
# --gpu_ids='4'

# train vgg16 weather
# python train.py \
# --name='three_view_long_share_d0.5_256_s1_google_lr0.005_vgg_v24.11_210ep_weather1' \
# --experiment_name='three_view_long_share_d0.5_256_s1_google_lr0.005_vgg_v24.11_210ep_weather1' \
# --data_dir='/home/wangtingyu/datasets/University-Release/train' \
# --views=3 \
# --droprate=0.5 \
# --extra \
# --share \
# --stride=1 \
# --h=256 \
# --w=256 \
# --lr=0.005 \
# --gpu_ids='3' \
# --iaa \
# --use_vgg \
# --multi_weather \
# --btnk 1 0 0 0 0 0 0 \
# --conv_norm='none' \
# --adain='a'

# python test_iaa.py \
# --name='three_view_long_share_d0.5_256_s1_google_lr0.005_vgg_v24.11_210ep_weather1' \
# --test_dir='/home/wangtingyu/datasets/University-Release/test' \
# --iaa \
# --gpu_ids='3'

# train ResnNet101 weather
# python train.py \
# --name='three_view_long_share_d0.5_256_s1_google_lr0.005_Res101_v24.11_210ep_weather' \
# --experiment_name='three_view_long_share_d0.5_256_s1_google_lr0.005_Res101_v24.11_210ep_weather' \
# --data_dir='/home/wangtingyu/datasets/University-Release/train' \
# --views=3 \
# --droprate=0.5 \
# --extra \
# --share \
# --stride=1 \
# --h=256 \
# --w=256 \
# --lr=0.005 \
# --gpu_ids='0' \
# --iaa \
# --use_res101 \
# --multi_weather \
# --btnk 0 0 0 0 0 0 0 \
# --conv_norm='none' \
# --adain='a'

# python test_iaa.py \
# --name='three_view_long_share_d0.5_256_s1_google_lr0.005_Res101_v24.11_210ep_weather' \
# --test_dir='/home/wangtingyu/datasets/University-Release/test' \
# --iaa \
# --gpu_ids='0'
