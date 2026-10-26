"""Native MuJoCo host using the official compiled FSM and ONNX policies.

No source checkout is imported as Python; immutable robot data and the shipped
native extension are loaded by path. This host is independent of mjlab and its
physics parity must be measured, never assumed. It controls simulation only.
"""
from pathlib import Path
import base64
import copy
import hashlib
import importlib.util
import importlib.machinery
import json
import math
import os
import sysconfig
import xml.etree.ElementTree as ET


def bundle_file_key(bundle,path):
    """Portable lookup key for the cross-platform upstream manifest."""
    return path.relative_to(bundle).as_posix()


def load_model(mujoco, xml, cache_dir=None, build_cache=False):
    """Compile in the image build; avoid the STL compiler's runtime memory spike.

    MJB files depend on MuJoCo's version and the complete scene, including its
    obstacle layout. A configured cache must contain that exact model; silently
    recompiling on a small host would kill the worker again.
    """
    if not cache_dir:
        return mujoco.MjModel.from_xml_string(xml)
    key = hashlib.sha256((mujoco.__version__+'\n'+xml).encode()).hexdigest()
    path = Path(cache_dir) / (key+'.mjb')
    if build_cache:
        path.parent.mkdir(parents=True, exist_ok=True)
        model = mujoco.MjModel.from_xml_string(xml)
        mujoco.mj_saveModel(model, str(path))
        return model
    if not path.is_file():
        raise RuntimeError('Compiled native model is missing. Rebuild the Docker image.')
    return mujoco.MjModel.from_binary_path(str(path))


class NativeJumper:
    def __init__(self, upstream, obstacles=(), *, build_model_cache=False):
        import mujoco
        import numpy as np
        import onnxruntime as ort
        import yaml
        self.mj, self.np = mujoco, np
        self.root = Path(upstream).resolve()
        self.servo = yaml.safe_load((self.root/'assets/jumper/motor/motor_config.yaml')
            .read_text())['motors']['joint_servo']['torque_speed']
        if self.servo['model'] != 'exp_decay_with_cutoff':
            raise RuntimeError('Unsupported source servo model')
        self.bundle = self.root / 'out/bundle_example/jumper'
        manifest = json.loads((self.bundle/'bundle.json').read_text())
        extensions = manifest['runtimes']['mjlab']['extensions']
        platform = sysconfig.get_platform()
        if platform.startswith('macosx'):
            platform = 'macosx-universal2'
        if platform not in extensions:
            raise RuntimeError(f'No upstream runtime for {platform}')
        extension = self.bundle/extensions[platform]['file']
        contracts_text = {k: (self.bundle/v['contract']).read_text()
                          for k, v in manifest['modes'].items()}
        contracts = {k: json.loads(v) for k,v in contracts_text.items()}
        self.contracts = contracts
        self.wire = contracts['locomotion']['wire_joint_order']
        # Manifest keys use forward slashes on Windows as well as Linux.
        needed = {bundle_file_key(self.bundle,extension), 'controller.toml'}
        needed.update(v['contract'] for v in manifest['modes'].values())
        needed.update(v['models']['onnx'] for v in manifest['modes'].values())
        needed.update(v['trajectory'] for v in manifest['modes'].values() if 'trajectory' in v)
        for name in needed:
            record = manifest['files'][name]
            data = (self.bundle/name).read_bytes()
            if hashlib.sha256(data).hexdigest() != record['sha256']:
                raise RuntimeError(f'Upstream bundle hash mismatch: {name}')
        loader = importlib.machinery.ExtensionFileLoader('mjrl_fsm', str(extension))
        spec = importlib.util.spec_from_file_location('mjrl_fsm', extension, loader=loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.extension_module = mod
        self.hz = max(c['control']['control_hz'] for c in contracts.values())
        self.dt = 1/self.hz
        limits = contracts['locomotion']['joint_limits']
        self.robot_spec = dict(joint_names=self.wire,
            joint_pos_lo=[limits[n][0] for n in self.wire],
            joint_pos_hi=[limits[n][1] for n in self.wire], output_rate_hz=self.hz,
            gait_gate_threshold=0.05)
        self.trajectories = {k:(self.bundle/v['trajectory']).read_text()
                             for k,v in manifest['modes'].items() if 'trajectory' in v}
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        self.sessions = {k:ort.InferenceSession(str(self.bundle/v['models']['onnx']),
                        sess_options=opts, providers=['CPUExecutionProvider'])
                         for k,v in manifest['modes'].items()}
        self.input_names={k:session.get_inputs()[0].name for k,session in self.sessions.items()}
        self.velocity_buffer=np.zeros(6)
        s=self.servo;rpm=2*math.pi/60
        self.motor_corner=s['corner_speed_rpm']*rpm
        self.motor_decay=s['decay_speed_rpm']*rpm
        self.motor_cutoff=s['cutoff_speed_rpm']*rpm
        self.motor_continuous=s['thermal_continuous_torque_nm']
        self.motor_plateau=s['plateau_torque_nm']
        self.thermal_tau=s['peak_duration_s']/math.log(1/(1-(self.motor_continuous/self.motor_plateau)**2))
        tree = ET.parse(self.root/'assets/jumper/jumper.xml')
        xml = tree.getroot()
        xml.find('compiler').set('meshdir',str(self.root/'assets/jumper'))
        visual=xml.find('visual')
        ET.SubElement(visual,'headlight',ambient='0.6 0.6 0.6',diffuse='0.7 0.7 0.7',
                      specular='0.15 0.15 0.15')
        asset=xml.find('asset')
        ET.SubElement(asset,'texture',name='mission_grid',type='2d',builtin='checker',
                      rgb1='0.73 0.78 0.69',rgb2='0.65 0.72 0.60',width='256',height='256')
        ET.SubElement(asset,'material',name='mission_ground',texture='mission_grid',
                      texrepeat='20 20',reflectance='0.05')
        world = xml.find('worldbody')
        ET.SubElement(world,'geom',name='mission_floor',type='plane',size='20 20 0.1',
                      material='mission_ground', friction='1 0.01 0.01')
        ET.SubElement(world,'light',pos='0 -3 5',dir='0 0 -1',diffuse='0.9 0.9 0.9')
        slots={}
        for i,obstacle in enumerate(obstacles):
            x,y,hx,hy=obstacle[:4]
            enabled=True if len(obstacle)==4 else bool(obstacle[4])
            if len(obstacle)>4:slots[tuple(obstacle[5:7])]=f'wall_{i}'
            ET.SubElement(world,'geom',name=f'wall_{i}',type='box',
                          pos=f'{x} {y} 0.15',size=f'{hx} {hy} 0.15',
                          rgba=f'0.53 0.61 0.47 {1 if enabled else 0}',
                          contype='1' if enabled else '0',
                          conaffinity='1' if enabled else '0',friction='1 0.01 0.01')
        # Preserve the shipped XML's collision settings. Visual-only meshes
        # retain zero contact masks; this independent host is not mjlab.
        self.model = load_model(mujoco, ET.tostring(xml,encoding='unicode'),
                                os.environ.get('NATIVE_MODEL_CACHE'), build_model_cache)
        self.data = mujoco.MjData(self.model)
        self.obstacle_geoms={cell:mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_GEOM,name)
                             for cell,name in slots.items()}
        self.obstacle_defaults={cell:int(self.model.geom_contype[gid])
                                for cell,gid in self.obstacle_geoms.items()}
        ids = [mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_JOINT,n) for n in self.wire]
        if min(ids) < 0:
            raise RuntimeError('Model and bundle joint names disagree')
        self.qadr = self.model.jnt_qposadr[ids]
        self.vadr = self.model.jnt_dofadr[ids]
        self.base = mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_BODY,'base_link')
        self.torque = np.zeros(len(self.wire))
        self.temperature = np.zeros(len(self.wire))
        self.control = (0.,0.,0.)
        self.pending_keys = []
        self.release_keys = []
        self.last_motion = None
        self.renderer = None
        self.render_model=None
        self.visual_ids=[i for i in range(self.model.ngeom)
                         if int(self.model.geom_group[i])==2 and int(self.model.geom_dataid[i])>=0]
        self.logs = []
        self.reset()

    def reset(self):
        for cell,enabled in self.obstacle_defaults.items():
            gid=self.obstacle_geoms[cell]
            self.model.geom_contype[gid]=enabled
            self.model.geom_conaffinity[gid]=enabled
            self.model.geom_rgba[gid,3]=float(enabled)
        self.mj.mj_resetData(self.model,self.data)
        home = self.contracts['locomotion']['default_joint_pos']
        self.data.qpos[2] = self.contracts['locomotion']['base_height']
        self.data.qpos[3] = 1
        self.data.qpos[self.qadr] = [home[n] for n in self.wire]
        self.torque[:] = 0
        self.temperature[:] = 0
        self.control = (0.,0.,0.)
        self.pending_keys.clear()
        self.release_keys.clear()
        self.fsm = self.extension_module.Fsm((self.bundle/'controller.toml').read_text(),
             {k:json.dumps(v) for k,v in self.contracts.items()},self.robot_spec,
             trajectories=self.trajectories, operators=True)
        self.mj.mj_forward(self.model,self.data)

    def stop(self):
        self.control = (0.,0.,0.)
        # Ctrl release is the bundle's declared leave-motion binding.
        # This is a controlled motion cancellation, not a physical E-stop.
        self.pending_keys = ['key_left_ctrl']
        self.last_motion = None

    def motion(self,name):
        names = {'wave':'key_1','bow':'key_2','paw':'key_3','salute':'key_4',
                 'celebrate':'key_1','curious':'key_3'}
        if name not in names:
            raise ValueError('Unknown motion')
        self.control = (0.,0.,0.)
        self.pending_keys = (['key_left_ctrl'] if name=='celebrate' else [])+[names[name]]
        self.last_motion = name

    def set_obstacle(self,cell,enabled):
        if tuple(cell) not in self.obstacle_geoms:
            raise ValueError('This native scene was loaded without mutable obstacle slots')
        gid=self.obstacle_geoms[tuple(cell)]
        self.model.geom_contype[gid]=int(enabled)
        self.model.geom_conaffinity[gid]=int(enabled)
        self.model.geom_rgba[gid,3]=1 if enabled else 0
        self.mj.mj_forward(self.model,self.data)

    def step(self, seconds=None):
        np,mj = self.np,self.mj
        count = 1 if seconds is None else max(1,round(seconds/self.dt))
        for _ in range(count):
            now=round(self.data.time*1e6)
            # MuJoCo free-joint rotational qvel is body local, but objectVelocity
            # explicitly requests local frame and avoids relying on that convention.
            vel=self.velocity_buffer
            mj.mj_objectVelocity(self.model,self.data,mj.mjtObj.mjOBJ_BODY,self.base,vel,1)
            self.fsm.set_state(self.data.qpos[self.qadr].tolist(),
                self.data.qvel[self.vadr].tolist(),self.torque.tolist(),
                self.data.xquat[self.base].tolist(),vel[:3].tolist(),now)
            for key in self.release_keys:
                self.fsm.set_key(key,False,now)
            self.release_keys=self.pending_keys
            self.pending_keys=[]
            for key in self.release_keys:
                self.fsm.set_key(key,True,now)
            vx,vy,wz=self.control
            # Normalized pad values; scaling remains the bundle's responsibility.
            # The upstream posture pad has +Ly down and +Lx right. Rx's outer
            # half turns; its inner half twists the body instead of turning.
            rx=0.0 if abs(wz)<0.01 else -math.copysign(0.5+0.5*min(1,abs(wz)),wz)
            self.fsm.set_pad_frame([],{'Ly':-vx,'Lx':-vy,'Rx':rx},now_us=now)
            mode=self.fsm.tick(now)
            if mode is not None:
                session=self.sessions[mode]
                obs=np.asarray([self.fsm.observation()],dtype=np.float32)
                action=session.run(None,{self.input_names[mode]:obs})[0][0]
                self.fsm.resume(action.tolist())
            target=np.asarray(self.fsm.positions())
            kp,kd=np.asarray(self.fsm.kp()),np.asarray(self.fsm.kd())
            # Native PD host: preserve contract targets and nonlinear speed cap.
            # Thermal cap follows the source asset's first-order approximation.
            for _ in range(round(self.dt/self.model.opt.timestep)):
                speed=np.abs(self.data.qvel[self.vadr])
                limit=self.motor_plateau*np.exp(-np.maximum(0,speed-self.motor_corner)/self.motor_decay)
                limit[speed>=self.motor_cutoff]=0
                continuous=self.motor_continuous
                limit=np.where(self.temperature>=1,np.minimum(limit,continuous),limit)
                self.torque=np.clip(kp*(target-self.data.qpos[self.qadr])-
                    kd*self.data.qvel[self.vadr],-limit,limit)
                self.temperature += self.model.opt.timestep/self.thermal_tau*(
                    (self.torque/continuous)**2-self.temperature)
                self.data.qfrc_applied[:]=0
                self.data.qfrc_applied[self.vadr]=self.torque
                mj.mj_step(self.model,self.data)
            if not np.all(np.isfinite(self.data.qpos)):
                raise RuntimeError('Nonfinite physics state')
            self.logs.extend(self.fsm.take_log())

    def state(self):
        q=self.data.xquat[self.base]
        yaw=math.atan2(2*(q[0]*q[3]+q[1]*q[2]),1-2*(q[2]**2+q[3]**2))
        tilt=math.acos(max(-1,min(1,self.data.xmat[self.base][8])))
        return dict(x=float(self.data.qpos[0]),y=float(self.data.qpos[1]),
                    z=float(self.data.qpos[2]),yaw=yaw,tilt=tilt,
                    mode=self.fsm.mode,running=self.fsm.running_policy,
                    sim_time=float(self.data.time),backend='mujoco-official-jumper',
                    max_torque=float(abs(self.torque).max()))

    def scene_description(self):
        """Exact source visual mesh geometry, reused by the browser renderer."""
        m=self.model;meshes={};geoms=[]
        for gid in self.visual_ids:
            mid=int(m.geom_dataid[gid]);key=str(mid)
            if key not in meshes:
                va,vn=int(m.mesh_vertadr[mid]),int(m.mesh_vertnum[mid])
                fa,fn=int(m.mesh_faceadr[mid]),int(m.mesh_facenum[mid])
                meshes[key]=dict(vertices=base64.b64encode(m.mesh_vert[va:va+vn].astype('<f4').tobytes()).decode(),
                    triangles=base64.b64encode(m.mesh_face[fa:fa+fn].astype('<u4').tobytes()).decode())
            geoms.append(dict(id=gid,mesh=key,color=m.geom_rgba[gid].tolist()))
        return dict(schema='mission-visuals/1',meshes=meshes,geoms=geoms)

    def scene_pose(self):
        return [[gid,*self.data.geom_xpos[gid].tolist(),*self.data.geom_xmat[gid].tolist()]
                for gid in self.visual_ids]

    def create_render_state(self):
        if self.render_model is None:
            self.render_model=copy.copy(self.model)
            self.render_data=self.mj.MjData(self.render_model)

    def capture_render_state(self):
        """Only this short copy shares the physics lock. All scene work is private."""
        self.create_render_state()
        self.mj.mj_copyData(self.render_data,self.render_model,self.data)
        for name in ('geom_rgba','geom_contype','geom_conaffinity'):
            self.np.copyto(getattr(self.render_model,name),getattr(self.model,name))

    def prepare_render(self,width=640,height=426,eco=False,capture=True):
        if capture:self.capture_render_state()
        if self.renderer is None:
            self.renderer=self.mj.Renderer(self.render_model,height=height,width=width)
            self.render_options=self.mj.MjvOption()
            # Collision hulls otherwise draw on top of the visual meshes.
            # Floor/walls use group 0, and the real robot visuals use group 2.
            self.render_options.geomgroup[1]=0
            self.camera=self.mj.MjvCamera()
            self.camera.azimuth=125
            self.camera.elevation=-70
            self.camera.distance=1.45
        self.camera.lookat[:]=self.render_data.qpos[:3]
        self.renderer.update_scene(self.render_data,camera=self.camera,scene_option=self.render_options)
        self.renderer.scene.flags[self.mj.mjtRndFlag.mjRND_REFLECTION]=False
        self.renderer.scene.flags[self.mj.mjtRndFlag.mjRND_SHADOW]=not eco

    def finish_render(self):
        """GPU readback uses only the private scene; it must not block commands."""
        return self.renderer.render().copy()

    def render(self,width=640,height=426):
        self.prepare_render(width,height)
        return self.finish_render()

    def close(self):
        if self.renderer is not None:
            self.renderer.close()
