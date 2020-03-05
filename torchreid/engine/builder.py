from torchreid.engine import (
    ImageSoftmaxEngine, ImageAMSoftmaxEngine, VideoSoftmaxEngine,
    ImageTripletEngine, VideoTripletEngine
)


def build_engine(cfg, datamanager, model, optimizer, scheduler, writer=None):
    if cfg.data.type == 'image':
        if cfg.loss.name == 'softmax':
            engine = ImageSoftmaxEngine(
                datamanager,
                model,
                optimizer=optimizer,
                scheduler=scheduler,
                use_gpu=cfg.use_gpu,
                label_smooth=cfg.loss.softmax.label_smooth
            )
        elif cfg.loss.name == 'am_softmax':
            engine = ImageAMSoftmaxEngine(
                datamanager,
                model,
                optimizer,
                cfg.reg,
                cfg.metric_losses,
                cfg.attr_losses,
                cfg.data.transforms.batch_transform,
                scheduler,
                cfg.use_gpu,
                conf_penalty=cfg.loss.softmax.conf_penalty,
                softmax_type='am',
                m=cfg.loss.softmax.m,
                s=cfg.loss.softmax.s,
                writer=writer
            )
        else:
            engine = ImageTripletEngine(
                datamanager,
                model,
                optimizer=optimizer,
                margin=cfg.loss.triplet.margin,
                weight_t=cfg.loss.triplet.weight_t,
                weight_x=cfg.loss.triplet.weight_x,
                scheduler=scheduler,
                use_gpu=cfg.use_gpu,
                label_smooth=cfg.loss.softmax.label_smooth,
                conf_penalty=cfg.loss.softmax.conf_penalty
            )
    else:
        if cfg.loss.name == 'softmax':
            engine = VideoSoftmaxEngine(
                datamanager,
                model,
                optimizer=optimizer,
                scheduler=scheduler,
                use_gpu=cfg.use_gpu,
                label_smooth=cfg.loss.softmax.label_smooth,
                conf_penalty=cfg.loss.softmax.conf_penalty,
                pooling_method=cfg.video.pooling_method
            )
        else:
            engine = VideoTripletEngine(
                datamanager,
                model,
                optimizer=optimizer,
                margin=cfg.loss.triplet.margin,
                weight_t=cfg.loss.triplet.weight_t,
                weight_x=cfg.loss.triplet.weight_x,
                scheduler=scheduler,
                use_gpu=cfg.use_gpu,
                label_smooth=cfg.loss.softmax.label_smooth,
                conf_penalty=cfg.loss.softmax.conf_penalty
            )

    return engine
