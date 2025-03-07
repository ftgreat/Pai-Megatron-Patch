# Copyright (c) 2023 Alibaba PAI and Nvidia Megatron-LM Team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import torch.nn.functional as F

from megatron.core.model_parallel_config import ModelParallelConfig
from megatron.core.utils import init_method_normal, scaled_init_method_normal


@dataclass
class TransformerConfig(ModelParallelConfig):
    """Configuration object for megatron-core transformers.

        Args:
            num_layers (int): Number of transformer layers in a transformer block.
            hidden_size (int): Transformer hidden size.
            ffn_hidden_size (int): Transformer Feed-Forward Network hidden size. This is set to 4*hidden_size if not provided. Defaults to None.')
            num_attention_heads (int): Number of transformer attention heads.
            kv_channels (int): Projection weights dimension in multi-head attention. This is set to hidden_size // num_attention_heads if not provided. Defaults to None.
            num_query_groups (int): Number of query groups for group query attention. If None, normal attention is used.
            hidden_dropout (float): Dropout probability for transformer hidden state. Defaults to 0.1.
            attention_dropout (float): Post attention dropout probability. Defaults to 0.1.
            fp32_residual_connection (bool): If true, move residual connections to fp32.
            apply_residual_connection_post_layernorm (bool): If true, uses the original BERT residule connection ordering. Defaults to False.
            layernorm_epsilon (float): Layernorm epsilon. Defaults to 1e-5.
            layernorm_zero_centered_gamma (bool): if set to 'True', the LayerNorm is adjusted to center the gamma values around 0. This improves numerical stability. Defaults to False.
            add_bias_linear (bool): Include a bias term in all linear layers (QKV projections, after core attention, and two in MLP layer). Default is True.
            gated_linear_unit (bool): Use a gated linear unit for the first linear layer in the MLP. Defaults to False.
            activation_func (Callable): Activation function to use for the non-linearity in the MLP. Defaults to F.gelu.
            num_moe_experts (int): Number of experts to use for MoE layer. When set, it replaces MLP with MoE layer. Defaults to None (no MoE).
            init_method (Callable): Method to initialize weights. Note that bias is always set to zero. Should be a function that takes a single Tensor and initializes it. Defaults to megatron.core.utils.init_method_normal(init_method_std) which is torch nn init normal with mean=0.0 and std=init_method_Std.
            output_layer_init_method (Callable): Method to initialize weights of the output layer of both attention and MLP blocks. Defaults to megatron.core.utils.scaled_init_method_normal(init_method_std) which is torch nn init normal with mean=0.0 and std=init_method_std / math.sqrt(2.0 * num_layers).
            init_method_std (float): Standard deviation of the zero mean normal for the default initialization method, not used if init_method and output_layer_init_method are provided. Defaults to 0.02.
            apply_query_key_layer_scaling (bool): If true, scale Q * K^T by 1 / layer-number. Defaults to True.
            attention_softmax_in_fp32 (bool): If true, run attention masking and softmax in fp32. This should be true if apply_query_key_layer_scaling is true.
            bias_gelu_fustion (bool): If true, fuses bias and gelu. Defaults to False.
            masked_softmax_fusion (bool): If true, uses softmax fusion.
            persist_layer_norm (bool): If true, uses the persistent fused layer norm kernel. This kernel only supports a fixed set of hidden sizes. Defaults to False.
            bias_dropout_fusion (bool): If true, uses bias dropout fusion.
            recompute_granularity (str): megatron-core supports 'selective' activation checkpointing where only the memory intensive part of attention is checkpointed.  These memory intensive activations are also less compute intensive which makes activation checkpointing more efficient for LLMs (20B+).  See Reducing Activation Recomputation in Large Transformer Models: https://arxiv.org/abs/2205.05198 for more details.  'full' will checkpoint the entire transformer layer.  Must be 'selective' or 'full'. 'selective' always uses all layers. Defaults to None.
            recompute_method (str): uniform will uniformly divide the total number of transformer layers in a transformer block and recompute the input activation of each divided chunk at the specified granularity.  block will recompute the input activations for only a set number of transformer layers per pipeline stage.  The rest of the layers in the pipeline stage  will not have any activations recomputed.  Must be 'uniform' or 'block'. Defaults to None.
            recompute_num_layers (int): When recompute_method is uniform, recompute_num_layers is the number of transformer layers in each uniformly divided recompute unit.  When recompute_method is block, recompute_num_layers is the number of transformer layers to recompute within each pipeline stage.  Must be None for 'selective' activation checkpointing. Defaults to None.
            distribute_saved_activations (bool): If true, distribute recomputed activations across the model parallel group. Defaults to None.
            fp8 (str): If set, enables the use of FP8 precision through Transformer Engine. There are 2 predefined choices: (1) 'e4m3' uniformly uses e4m3 for all FP8 tensors, (2) 'hybrid' uses e4m3 for all FP8 activation and weight tensors and e5m2 for all FP8 output activation gradient tensors. Defaults to None.
            fp8_margin (int): Margin for the scaling factor computation.
            fp8_interval (int): Controls how often the scaling factor is recomputed.
            fp8_amax_history_len (int): The length of the amax history window used for scaling factor computation.
            fp8_amax_compute_algo (str): Algorithm used for choosing the `amax` value for the scaling factor computation. There are 2 predefined choices: `max` chooses the largest `amax` in the history window, while `most_recent` always chooses the most recently seen value.
            fp8_wgrad (bool): When set to False, override FP8 config options and do the wgrad computation in higher precision. Defaults to True.
            clone_scatter_output_in_embedding (bool): When set to true, clone the output of scatter_to_sequence_parallel_region in embedding layer to facilitate garbage collection of input.
            normalization (str): Swtich b/w `LayerNorm` and `RMSNorm` as normalization layers. For now, these are primarily used by Transformer-Engine's layers like `LayerNormLinear`. Default value is `LayerNorm`.
            window_size ((int,int) or None): If not None, then will use sliding window attention. The size of the window is specified by the numbers inside the tuple; -1 is special value meaning "infinite window size".
            moe_router_load_balancing_type (str): Determines the load balancing strategy for the router. "aux_loss" corresponds to the load balancing loss used in GShard and SwitchTransformer, "sinkhorn" corresponds to the balancing algorithm used in S-BASE, and "None" implies no load balancing. The default is "aux_loss".
            moe_router_topk (int): Number of experts to route to for each token. The default is 2.
            moe_grouped_gemm (bool): When there are multiple experts per rank, compress multiple local (potentially small)
            gemms in a single kernel launch to improve the utilization and performance by leveraging the Grouped GEMM feature introduced since CUTLASS 2.8 (https://github.com/fanshiqing/grouped_gemm).
            moe_aux_loss_coeff (float): Scaling coefficient for the aux loss: a starting value of 1e-2 is recommended.
            moe_z_loss_coeff (float): Scaling coefficient for the z-loss: a starting value of 1e-3 is recommended.
            moe_input_jitter_eps (float): Add noise to the input tensor by applying jitter with a specified epsilon value.
            moe_token_dropping (bool): This feature involves selectively dropping and padding tokens for each expert to achieve a specified capacity, similar to GShard, Switch-Transformer, and DeepSpeed-MoE. Note: Currently unsupported.
    """

    # model architecture
    num_layers: int = 0
    hidden_size: int = 0
    num_attention_heads: int = 0
    num_query_groups: int = None

    ffn_hidden_size: int = None
    kv_channels: int = None
    hidden_dropout: float = 0.1
    attention_dropout: float = 0.1
    fp32_residual_connection: bool = False
    # @jcasper should we keep this option?
    apply_residual_connection_post_layernorm: bool = False
    layernorm_epsilon: float = 1e-5
    layernorm_zero_centered_gamma: bool = False
    add_bias_linear: bool = True
    gated_linear_unit: bool = False
    activation_func: Callable = F.gelu
    num_moe_experts: int = None
    window_size: Optional[Tuple[int, int]] = None

    # initialization
    init_method: Callable = None
    output_layer_init_method: Callable = None
    init_method_std: float = 0.02

    # mixed-precision
    apply_query_key_layer_scaling: bool = False
    attention_softmax_in_fp32: bool = True

    # communication

    # fusion
    bias_activation_fusion: bool = False
    masked_softmax_fusion: bool = False
    persist_layer_norm: bool = False
    bias_dropout_fusion: bool = False  # TODO: this should be bias_dropout_add_fusion?
    apply_rope_fusion: bool = False

    # activation recomputation
    recompute_granularity: str = None
    recompute_method: str = None
    recompute_num_layers: int = None
    distribute_saved_activations: bool = None

    # fp8 related
    fp8: str = None
    fp8_margin: int = 0
    fp8_interval: int = 1
    fp8_amax_history_len: int = 1
    fp8_amax_compute_algo: str = "most_recent"
    fp8_wgrad: bool = True

    # miscellaneous
    clone_scatter_output_in_embedding: bool = True

    # experimental section (TODO: move to apt. section above once stable)
    normalization: bool = "LayerNorm"  # alt value supported by TE: "RMSNorm"

    # MoE related
    moe_router_load_balancing_type: str = "aux_loss"
    moe_router_topk: int = 2
    moe_grouped_gemm: bool = False
    moe_aux_loss_coeff: float = 0  # 1e-2 would be a good start value for load balance loss.
    moe_z_loss_coeff: float = None  # 1e-3 would be a good start value for z-loss
    moe_input_jitter_eps: float = None
    moe_token_dropping: bool = False  # TODO: Support token dropping.

    def __post_init__(self):
        """ Python dataclass method that is used to modify attributes after initialization.
            See https://docs.python.org/3/library/dataclasses.html#post-init-processing for more details.
        """
        super().__post_init__()
        if self.fp16 and self.bf16:
            raise ValueError(
                f'Only one of self.fp16: {self.fp16} and self.bf16 {self.bf16} should be True.'
            )

        if self.num_attention_heads % self.tensor_model_parallel_size != 0:
            raise ValueError(
                f"num_attention_heads ({self.num_attention_heads}) must be a multiple of "
                f"tensor_model_parallel_size ({self.tensor_model_parallel_size})."
            )

        if self.ffn_hidden_size is None:
            self.ffn_hidden_size = 4 * self.hidden_size

        if self.kv_channels is None:
            self.kv_channels = self.hidden_size // self.num_attention_heads

        if self.num_query_groups is None:
            self.num_query_groups = self.num_attention_heads

        if self.num_query_groups % self.tensor_model_parallel_size != 0:
            raise ValueError(
                f"num_query_groups ({self.num_query_groups}) must be a multiple of "
                f"tensor_model_parallel_size ({self.tensor_model_parallel_size})."
            )

        if self.apply_query_key_layer_scaling:
            self.attention_softmax_in_fp32 = True

        if self.expert_model_parallel_size > 1 and self.num_moe_experts is None:
            raise ValueError(f'num_moe_experts must be non None to use expert-parallel.')

        if self.cpu_offloading_num_layers < 0 or self.cpu_offloading_num_layers >= self.num_layers:
            raise ValueError(
                f'CPU offloading can be done only for layers less than {self.num_layers}'
            )

        if self.cpu_offloading and self.pipeline_model_parallel_size > 1:
            raise ValueError(
                f'Currently there is no support for Pipeline parallelism with CPU offloading'
            )

        if self.cpu_offloading and self.recompute_granularity is not None:
            raise ValueError(
                f'CPU offloading does not work when activation recomputation is enabled'
            )

        if self.recompute_granularity is not None:
            if not self.recompute_granularity in ['full', 'selective']:
                raise ValueError(
                    f'When using recompute_granuarlity: {self.recompute_granularity} must be "full" or "selective".'
                )

            if self.recompute_method is not None:
                if not self.recompute_method in ['block', 'uniform']:
                    raise ValueError(
                        f'recompute_method: {self.recompute_method} must be "block" or "uniform".'
                    )
            elif self.recompute_granularity != 'selective':
                raise ValueError(
                    f'Using recompute_granularity: {self.recompute_granularity} so recompute_method must be "block" or "uniform"'
                )

            if self.recompute_granularity != 'selective' and self.recompute_num_layers is None:
                raise ValueError(
                    f'When using recompute_granularity: {self.recompute_granularity} recompute_num_layers must be between '
                    f'1 and num_layers_per_pipeline_rank: {self.num_layers // self.pipeline_model_parallel_size}'
                )
            elif (
                self.recompute_granularity == 'selective' and self.recompute_num_layers is not None
            ):
                raise ValueError(
                    f'When using recompute_granularity: {self.recompute_granularity} recompute_num_layers must be None.'
                )

            if self.distribute_saved_activations and self.sequence_parallel:
                raise ValueError(
                    f'distribute_saved_activations: {self.distribute_saved_activations} must be false when sequence parallel is enabled: {self.sequence_parallel}'
                )

            if self.virtual_pipeline_model_parallel_size is not None:
                if not self.num_layers % self.virtual_pipeline_model_parallel_size == 0:
                    raise ValueError(
                        f'num_layers: {self.num_layers} must be divisible by virtual_model_parallel_size {self.virtual_pipeline_model_parallel_size}'
                    )

        if self.apply_query_key_layer_scaling:
            self.attention_softmax_in_fp32 = True

        if self.bias_activation_fusion:
            if self.activation_func not in [F.gelu, F.silu]:
                raise ValueError(
                    "When bias_activation_fusion is True, activation function should be either gelu or swiglu"
                )
            if self.activation_func == F.gelu and not self.add_bias_linear:
                raise ValueError(
                    "When bias_activation_fusion is True and activation function is gelu, add_bias_linear must also be True."
                )

        if self.init_method is None:
            self.init_method = init_method_normal(self.init_method_std)

        if self.output_layer_init_method is None:
            self.output_layer_init_method = scaled_init_method_normal(
                self.init_method_std, self.num_layers
            )
