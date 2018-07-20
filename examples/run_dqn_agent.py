import tensorflow as tf

from rltf.agents        import AgentDQN
from rltf.agents        import AgentBDQN
from rltf.envs          import wrap_dqn
from rltf.models        import BDQN
from rltf.models        import BDQN_IDS
from rltf.models        import BDQN_UCB
from rltf.models        import BstrapDQN
from rltf.models        import BstrapDQN_IDS
from rltf.models        import BstrapDQN_UCB
from rltf.models        import BstrapDQN_Ensemble
from rltf.models        import BstrapDQNQR_IDS
from rltf.models        import BstrapDQNC51_IDS
from rltf.models        import DDQN
from rltf.models        import DQN
from rltf.models        import C51
from rltf.models        import C51TS
from rltf.models        import QRDQN
from rltf.models        import QRDQNTS
from rltf.models        import DUBstrapC51
from rltf.models        import DUBstrapC51_IDS
from rltf.models        import DUBstrapQRDQN
from rltf.models        import DUBstrapQRDQN_IDS
from rltf.optimizers    import OptimizerConf
from rltf.schedules     import ConstSchedule
from rltf.schedules     import PiecewiseSchedule
from rltf.utils         import rltf_log
from rltf.utils         import maker
from rltf.utils         import cmdargs
from rltf.utils         import layouts


def parse_args():

  model_types = ["DQN", "DDQN", "C51", "QRDQN",
                 "BstrapDQN", "BstrapDQN_UCB", "BstrapDQN_Ensemble", "BstrapDQN_IDS",
                 "BstrapDQNC51_IDS", "BstrapDQNQR_IDS",
                 "BDQN", "BDQN_TS", "BDQN_UCB", "BDQN_IDS", "C51TS", "QRDQNTS",
                 "DUBstrapC51", "DUBstrapC51_IDS", "DUBstrapQRDQN", "DUBstrapQRDQN_IDS",]
  s2b         = cmdargs.str2bool

  args = [
    ('--env-id',        dict(required=True,  type=str,   help='full environment name')),
    ('--model',         dict(required=True,  type=str,   choices=model_types)),

    ('--learn-rate',    dict(default=5e-5,   type=float, help='learn rate',)),
    ('--batch-size',    dict(default=32,     type=int,   help='batch size for training the net',)),
    ('--memory-size',   dict(default=10**6,  type=int,   help='size of the replay buffer',)),
    ('--adam-epsilon',  dict(default=.01/32, type=float, help='epsilon for Adam optimizer')),
    ('--n-heads',       dict(default=10,     type=int,   help='number of heads for BstrapDQN')),
    ('--epsilon-eval',  dict(default=0.001,  type=float, help='epsilon value during evaluation')),
    ('--explore-decay', dict(default=10**6,  type=int,   help='# *agent* steps to decay epsilon to 0.01; \
      if <=0, epsilon=0 for the whole run')),

    ('--warm-up',       dict(default=50000,  type=int,   help='# *agent* steps before training starts')),
    ('--train-freq',    dict(default=4,      type=int,   help='train frequency in # *agent* steps')),
    ('--update-freq',   dict(default=10000,  type=int,   help='update target freq in # *param updates*')),
    ('--stop-step',     dict(default=5*10**7,type=int,   help='steps to run the *agent* for')),
    ('--huber-loss',    dict(default=True,   type=s2b,   help='use huber loss')),

    ('--eval-freq',     dict(default=250000, type=int,   help='freq in # *agent* steps to run eval')),
    ('--eval-len',      dict(default=125000, type=int,   help='# *agent* steps to run eval each time')),
    ('--eval-ep-steps', dict(default=None,   type=int,   help='max episode *env* steps in *eval* mode')),
    ('--train-ep-steps',dict(default=None,   type=int,   help='max episode *env* steps in *train* mode')),

    ('--n-stds',        dict(default=0.1,    type=float, help='uncertainty scale for UCB and IDS')),
    ('--tau',           dict(default=0.01,   type=float, help='BLR prior covariance')),
    ('--sigma-e',       dict(default=1.0,    type=float, help='BLR observation noise')),
  ]

  return cmdargs.parse_args(args)


def make_agent():

  args = parse_args()

  # Get the model directory path
  if args.restore_model is None:
    model_dir   = maker.make_model_dir(args.model, args.env_id)
    restore_dir = args.reuse_model
  else:
    model_dir   = args.restore_model
    restore_dir = args.restore_model

  # Configure loggers
  rltf_log.conf_logs(model_dir)

  # Get the model-specific settings
  model = eval(args.model)
  agent = AgentDQN

  if   args.model in ["DQN", "DDQN"]:
    model_kwargs  = dict(huber_loss=args.huber_loss)
  elif args.model in ["BstrapDQN", "BstrapDQN_IDS", "BstrapDQN_UCB", "BstrapDQN_Ensemble"]:
    model_kwargs  = dict(huber_loss=args.huber_loss, n_heads=args.n_heads)
  elif args.model in ["BstrapDQNC51_IDS", "DUBstrapC51", "DUBstrapC51_IDS",]:
    model_kwargs  = dict(n_heads=args.n_heads, V_min=-10, V_max=10, N=51)
  elif args.model in ["BstrapDQNQR_IDS", "DUBstrapQRDQN", "DUBstrapQRDQN_IDS",]:
    model_kwargs  = dict(n_heads=args.n_heads, N=200, k=int(args.huber_loss))
  elif args.model in ["C51", "C51TS"]:
    model_kwargs  = dict(V_min=-10, V_max=10, N=51)
  elif args.model in ["QRDQN", "QRDQNTS"]:
    model_kwargs  = dict(N=200, k=int(args.huber_loss))
  elif args.model in ["BDQN", "BDQN_TS", "BDQN_IDS", "BDQN_UCB"]:
    model_kwargs  = dict(huber_loss=args.huber_loss, sigma_e=args.sigma_e, tau=args.tau)
    agent         = AgentBDQN

  if args.model.endswith("_IDS") or args.model.endswith("_UCB"):
    model_kwargs["n_stds"] = args.n_stds

  model_kwargs["gamma"] = args.gamma


  # Create the environments
  env_kwargs = dict(
    env_id=args.env_id,
    seed=args.seed,
    model_dir=model_dir,
    video_freq=args.video_freq,
    wrap=wrap_dqn,
    max_ep_steps_train=args.train_ep_steps,
    max_ep_steps_eval=args.eval_ep_steps,
  )
  env_train, env_eval = maker.make_envs(**env_kwargs)


  # Set the learning rate schedule
  learn_rate = ConstSchedule(args.learn_rate)

  # Cteate the optimizer configs
  opt_conf = OptimizerConf(tf.train.AdamOptimizer, learn_rate, epsilon=args.adam_epsilon)

  # Create the exploration schedule
  if args.explore_decay > 0:
    exploration = PiecewiseSchedule([(0, 1.0), (args.explore_decay, 0.01)], outside_value=0.01)
  else:
    exploration = ConstSchedule(0.0)

  plots_layout = layouts.layouts.get(args.model, None) if args.plot_video else None

  # Set the Agent class keyword arguments
  agent_kwargs = dict(
    env_train=env_train,
    env_eval=env_eval,
    train_freq=args.train_freq,
    warm_up=args.warm_up,
    stop_step=args.stop_step,
    eval_freq=args.eval_freq,
    eval_len=args.eval_len,
    batch_size=args.batch_size,
    model_dir=model_dir,
    log_freq=args.log_freq,
    save_freq=args.save_freq,
    restore_dir=restore_dir,
    plots_layout=plots_layout,
    confirm_kill=args.confirm_kill,
    reuse_regex=args.reuse_regex,
  )

  dqn_agent_kwargs = dict(
    model=model,
    model_kwargs=model_kwargs,
    opt_conf=opt_conf,
    exploration=exploration,
    update_target_freq=args.update_freq,
    memory_size=args.memory_size,
    obs_len=4,
    epsilon_eval=args.epsilon_eval,
  )

  kwargs = {**dqn_agent_kwargs, **agent_kwargs}

  # Log the parameters for model
  log_info = [("seed", args.seed), ("extra_info", args.extra_info)]
  log_info += kwargs.items()
  rltf_log.log_params(log_info, args)

  # Create the agent
  dqn_agent = agent(**kwargs)

  return dqn_agent, args


def main():
  # Create the agent
  dqn_agent, args = make_agent()

  # Build the agent and the TF graph
  dqn_agent.build()

  # Train or eval the agent
  if args.mode == 'train':
    dqn_agent.train()
  else:
    dqn_agent.eval()

  # Close on exit
  dqn_agent.close()


if __name__ == "__main__":
  main()
