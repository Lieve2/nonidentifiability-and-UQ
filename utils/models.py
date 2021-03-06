"""
Implementations of Bayesian models.

For neural networks, we describe the dimensions
with the following conventions, unless otherwise noted:

- The input X is generally a dataset with N rows and M features.
  In some cases, we may have a "stack" of R datasets
  (i.e. X may be a R-by-N-by-M tensor instead of the usual N-by-M matrix)
  but this case is not supported by our initial implementations.

- The output Y is generally an N-by-K matrix (for a K-output model)
  but may also be R-by-N-by-K, analogously with the input X.

- The weights W of a single neural network are stored
  as a 1-by-D matrix (for a network with D weights).
  When representing the weights of a set of S models
  (e.g. mutiple samples from a posterior), the weights
  may be stored in an S-by-D matrix. (Additionally,
  our implementation has an internal representation
  that uses a list of weights for each layer, but
  that version need not be exposed to the user.)

- In a latent variable model, the X and Y inputs follow the same
  conventions as above, but L latent features of Gaussian noise
  are appeneded to the input X to form an augmented input X'.
  Typically there is a single latent variable (i.e. L=1),
  but we have made our implementation flexible so that we can
  exeperiment with multiple latent variables.
  Additionally, Gaussian noise is added to each of the output Y
  (potentially with a different variance for each of the K outputs),
  to form a pertured output Y'.

In summary:
- R: number of "stacked" datasets for X and Y (and X' and Y').
- N: number of data points in X and Y (and X' and Y').
- M: number of features in X.
- K: number of outputs in Y.
- S: number of different models in W.
- D: number of weights in each model.
- L: number of latent noise inputs.
"""

import inspect
import re

from autograd import numpy as np
from autograd import grad
from autograd.misc.optimizers import adam

from utils.functions import log_gaussian, gaussian


class BayesianModel:

    """
    A Bayesian model for BNN LV.
    """
    
    def __init__(
        self,
        X, Y, nn,
        prior_weights_mean = 0.0,
        prior_weights_stdev = 1.0,
        prior_latents_mean = 0.0,
        prior_latents_stdev = 1.0,
        likelihood_stdev = 1.0,
        output_noise_stdev = 1.0,
        label = '',
    ):
        
        # Check inputs:
        assert len(X.shape)==2, f"Expects X to be N by M, not {X.shape}"
        assert len(Y.shape)==2, f"Expects Y to be N by K, not {Y.shape}"
        assert X.shape[0]==Y.shape[0], f"Expects X {X.shape} and Y {Y.shape} to have same first dimension."
        
        # Get dimensions:
        self.L = 1
        self.N = X.shape[0]
        self.M = X.shape[1]
        self.K = Y.shape[1]
        self.D = nn.D
        
        # Store parameters:
        self.X = X
        self.Y = Y
        self.nn = nn
        self.prior_weights_mean = prior_weights_mean
        self.prior_weights_stdev = prior_weights_stdev
        self.prior_latents_mean = prior_latents_mean
        self.prior_latents_stdev = prior_latents_stdev
        self.likelihood_stdev = likelihood_stdev
        self.output_noise_stdev = output_noise_stdev
        self.label = label

    @staticmethod
    def sum_over_samples(tensor):
        # Helper: Sum across all by the first dimension:
        num_samples = tensor.shape[0]
        return np.sum( tensor.reshape(num_samples,-1), axis=-1)

    def predict(self, X, W):
        return self.nn.forward(X=X, weights=W, input_noise='auto', output_noise='auto')
        
    def log_prior_weights(self, W):
        mu = self.prior_weights_mean
        sigma = self.prior_weights_stdev
        if len(W.shape)==2:
            return self.sum_over_samples( log_gaussian(x=W, mu=mu, sigma=sigma) )
        raise NotImplementedError(f"Expects W to have 2 dimensions, not {W.shape}.")
    
    def log_prior_latents(self, Z):
        mu = self.prior_latents_mean
        sigma = self.prior_latents_stdev
        if len(Z.shape)==2:
            return np.sum( log_gaussian(x=Z, mu=mu, sigma=sigma) ).reshape(1,-1)
        elif len(Z.shape)==3:
            return self.sum_over_samples( log_gaussian(x=Z, mu=mu, sigma=sigma) )
        raise NotImplementedError(f"Expects Z to have 2 or 3 dimensions, not {Z.shape}.")
        
    def log_prior(self, W, Z):
        return self.log_prior_weights(W) + self.log_prior_latents(Z)
    
    def log_likelihood(self, W, Z):
        mu = self.nn.forward(X=self.X, weights=W, input_noise=Z)
        sigma = self.likelihood_stdev
        if len(Z.shape)==2:
            return np.sum( log_gaussian(x=self.Y, mu=mu, sigma=sigma) )
        elif len(Z.shape)==3:
            return self.sum_over_samples(log_gaussian(x=self.Y, mu=mu, sigma=sigma) )
        raise NotImplementedError(f"Expects Z to have 2 or 3 dimensions, not {Z.shape}.")

    def likelihood(self, W, Z): #might be incorrect
        mu = self.nn.forward(X=self.X, weights=W, input_noise=Z)
        sigma = self.likelihood_stdev
        if len(Z.shape)==2:
            return np.sum( gaussian(x=self.Y, mu=mu, sigma=sigma) )
        elif len(Z.shape)==3:
            return self.sum_over_samples(gaussian(x=self.Y, mu=mu, sigma=sigma) )
        raise NotImplementedError(f"Expects Z to have 2 or 3 dimensions, not {Z.shape}.")

    def parameters(self, W, Z): #remove if not working
        mu = self.nn.forward(X=self.X, weights=W, input_noise=Z)
        sigma = self.likelihood_stdev
        return mu #, sigma

    def log_posterior(self, W, Z):
        return self.log_prior_weights(W) + self.log_prior_latents(Z) + self.log_likelihood(W, Z)

    def info(self):
        info = {
            'L' : self.L,
            'N' : self.N,
            'M' : self.M,
            'K' : self.K,
            'D' : self.D,
        }
        return info

    def description(self):
        description = ""
        for param_name in [
            'prior_weights_mean',
            'prior_weights_stdev',
            'prior_latents_mean',
            'prior_latents_stdev',
            'likelihood_stdev',
            'output_noise_stdev',
        ]:
            param_value = getattr(self, param_name)
            description += f"{param_name} = {param_value}\n"
        description += "\n"
        description += """
        def predict(X, W):
            return nn.forward(X=X, weights=W, input_noise='auto', output_noise='auto')
            
        def log_prior_weights(W):
            mu = prior_weights_mean
            sigma = prior_weights_stdev
            return np.sum( log_gaussian(x=W, mu=mu, sigma=sigma) )
        
        def log_prior_latents(Z):
            mu = prior_latents_mean
            sigma = prior_latents_stdev
            return np.sum( log_gaussian(x=Z, mu=mu, sigma=sigma) ).reshape(1,-1)
            
        def log_prior(W, Z):
            return log_prior_weights(W) + log_prior_latents(Z)
        
        def log_likelihood(W, Z):
            mu = nn.forward(X=X, weights=W, input_noise=Z)
            sigma = likelihood_stdev
            np.sum( log_gaussian(x=Y, mu=mu, sigma=sigma) )
        
        def log_posterior(W, Z):
            return log_prior_weights(W) + log_prior_latents(Z) + log_likelihood(W, Z)
        """
        description = re.sub(f'self\.','',description)
        return description

    def describe(self):
        print(self.description())

    def to_latex(self):
        prior_weights_mean = np.round(self.prior_weights_mean, 3)
        prior_weights_stdev = np.round(self.prior_weights_stdev, 3)
        prior_latents_mean = np.round(self.prior_latents_mean, 3)
        prior_latents_stdev = np.round(self.prior_latents_stdev, 3)
        likelihood_stdev = np.round(self.likelihood_stdev, 3)
        output_noise_stdev = np.round(self.output_noise_stdev, 3)
        s = "" if self.label is None else "\\textbf{{{} :}}\\\\".format(self.label)
        s += "W \\;\\sim\\; N(\\; {},\\; {}\\; ) \\\\".format( prior_weights_mean, prior_weights_stdev**2 )
        s += "Z \\;\\sim\\; N(\\; {},\\; {}\\; ) \\\\".format( prior_latents_mean, prior_latents_stdev**2 )
        s += "Y|W,Z \\;\\sim\\; N(\\; g_W(X),\\; {}\\; ) + N( 0, {} ) \\\\".format( likelihood_stdev**2, output_noise_stdev**2 )
        s += "W,Z|Y \\;\\sim\\; ? \\;\\rightarrow\\; \\text{{BNN LV}} \\\\".format()
        return s
        
    def display(self):
        from IPython.display import display, Math
        s = self.to_latex()
        s = Math(s)
        display(s)

    def _repr_html_(self):
        self.display()
        

    def predict(self, X, W):
        return self.nn.forward(X=X, weights=W, input_noise='auto', output_noise='auto')
        
    def log_prior_weights(self, W):
        mu = self.prior_weights_mean
        sigma = self.prior_weights_stdev
        if len(W.shape)==2:
            return self.sum_over_samples( log_gaussian(x=W, mu=mu, sigma=sigma) )
        raise NotImplementedError(f"Expects W to have 2 dimensions, not {W.shape}.")
    
    def log_prior_latents(self, Z):
        mu = self.prior_latents_mean
        sigma = self.prior_latents_stdev
        if len(Z.shape)==2:
            return np.sum( log_gaussian(x=Z, mu=mu, sigma=sigma) ).reshape(1,-1)
        elif len(Z.shape)==3:
            return self.sum_over_samples( log_gaussian(x=Z, mu=mu, sigma=sigma) )
        raise NotImplementedError(f"Expects Z to have 2 or 3 dimensions, not {Z.shape}.")
        
    def log_prior(self, W, Z):
        return self.log_prior_weights(W) + self.log_prior_latents(Z)
    
    def log_likelihood(self, W, Z):
        mu = self.nn.forward(X=self.X, weights=W, input_noise=Z)
        sigma = self.likelihood_stdev
        if len(Z.shape)==2:
            return np.sum( log_gaussian(x=self.Y, mu=mu, sigma=sigma) )
        elif len(Z.shape)==3:
            return self.sum_over_samples( log_gaussian(x=self.Y, mu=mu, sigma=sigma) )
        raise NotImplementedError(f"Expects Z to have 2 or 3 dimensions, not {Z.shape}.")
        
    
class SamplerModel:

    """
    A wrapper for connecting a Bayesian model to a sampler,
    which stacks weights and latent variables in a single `samples` matrix
    (S by (1*D+N*L)) that includes both model weights and latent variables.
    """
    
    def __init__(
        self,
        model,  # BayesianModel object.
    ):
        
        # Store wrapped model:
        self.model = model

        # Get properties of wrapped model:
        self.label = model.label
        self.X = model.X
        self.Y = model.Y
        self.nn = model.nn
        
        # Store dimensions of wrapped model:
        self.L = model.L
        self.N = model.N
        self.M = model.M
        self.K = model.K
        self.D = model.D
        
        # Store functions of wrapped model:
        self._log_prior = model.log_prior
        self._log_likelihood = model.log_likelihood
        self._log_posterior = model.log_posterior
        self._parameters = model.parameters #remove if not working
        self._likelihood = model.likelihood #remove if not working
    
    def stack(self, W, Z):
        if len(Z.shape)==2:
            assert (len(W.shape)==2), f"Expects an S by D matrix, not {W.shape}"
            assert Z.shape[0]==self.N, f"In 2D case, expects N ({self.N}) by L ({self.L}) matrix, not {Z.shape}"
            assert Z.shape[1]==self.L, f"In 2D case, expects N ({self.N}) by L ({self.L}) matrix, not {Z.shape}"
            Z = Z.reshape(1,*Z.shape)  # Add S=1 as first dimension.
        elif len(Z.shape)==3:
            assert (len(W.shape)==2), f"Expects an S by D matrix, not {W.shape}"
            assert Z.shape[-2]==self.N, f"In 3D case, expects S by N ({self.N}) by L ({self.L}) tensor, not {Z.shape}"
            assert Z.shape[-1]==self.L, f"In 3D case, expects S by N ({self.N}) by L ({self.L}) tensor, not {Z.shape}"
        else:
            raise NotImplementedError(f"Z should be two (N by L) or three (S by N by L) dimensions, not {Z.shape}")
        # Make sure both inputs have the same number of samples (or 1):
        S = max(W.shape[0],Z.shape[0])
        if (W.shape[0] not in {1,S}) or (Z.shape[0] not in {1,S}):
            ValueError(f"If either input has more than one sample, they must both has the same number; received {W.shape[0]} and {Z.shape[0]}.")
        # Broadcast both inputs to have size S:
        if W.shape[0]<S:
            assert W.shape[0]==1, f"W and Z must have same number of samples or 1 sample, but cannot broadcast two different size: {W.shape[0]} and {Z.shape[0]}"
            W = np.tile(W, reps=(S,1))  # Repeat S times along first axis and preserve other axis (D).
        if Z.shape[0]<S:
            assert Z.shape[0]==1, f"W and Z must have same number of samples or 1 sample, but cannot broadcast two different size: {W.shape[0]} and {Z.shape[0]}"
            Z = np.tile(Z, reps=(S,1,1))  # Repeat S times along first axis and preserve other axes (N and L).
        # Reshape and concatenate:
        W_flat = W.reshape(S,self.D)
        Z_flat = Z.reshape(S,self.N*self.L)
        samples = np.concatenate([W_flat,Z_flat],axis=-1)  # Create 1 by (1*D+N*L) matrix.
        return samples
    
    def unstack(self, samples):
        assert len(samples.shape)==2, f"Expects samples to be 2 dimenional."
        assert samples.shape[1]==(1*self.D)+(self.N*self.L), f"Expects samples to have a value for each weight and a value for each data point for each latent feature."
        S = samples.shape[0]
        if S==1:
            W = samples[:,:self.D].reshape(1,self.D)
            Z = samples[:,self.D:].reshape(self.N,self.L)  # 2 dimensions.
        else:
            W = samples[:,:self.D].reshape(S,self.D)
            Z = samples[:,self.D:].reshape(S,self.N,self.L)  # 3 dimensions.
        return W, Z

    def vectorize(self, func, W, Z):
        assert len(Z.shape)==3, "Vectorization is only defined for 3 dimension case."
        results = np.array([
            func(w.reshape(1,-1), z)
            for w, z in zip(W,Z)
        ]).flatten()
        assert len(results)==Z.shape[0], f"Vectorization over S samples had unexpected results: {results} ."
        return results

    def predict(self, X, samples):
        W, _ = self.unstack(samples)
        # if len(Z.shape)==3:
        #     return self.vectorize(self.model.predict, W=W, Z=Z)
        return self.model.predict(X=X, W=W)
        
    def log_prior(self, samples):
        W, Z = self.unstack(samples)
        # if len(Z.shape)==3:
        #     return self.vectorize(self.model.log_prior, W=W, Z=Z)
        return self.model.log_prior(W=W, Z=Z)
    
    def log_likelihood(self, samples):
        W, Z = self.unstack(samples)
        # if len(Z.shape)==3:
        #     return self.vectorize(self.model.log_likelihood, W=W, Z=Z)
        return self.model.log_likelihood(W=W, Z=Z)

    def likelihood(self, samples):
        W, Z = self.unstack(samples)
        return self.model.likelihood(W=W, Z=Z)

    def parameters(self,samples): #remove if not working
        W, Z = self.unstack(samples)
        return self.model.parameters(W=W, Z=Z)

    def log_posterior(self, samples):
        W, Z = self.unstack(samples)
        # if len(Z.shape)==3:
        #     return self.vectorize(self.model.log_posterior, W=W, Z=Z)
        return self.model.log_posterior(W=W, Z=Z)

    def ppo(self, samples):
        for sample in samples:
            value = min()

    def info(self):
        return self.model.info()
    
    def description(self):
        return self.model.description()
    
    def describe(self):
        self.model.describe()

    def display(self):
        from IPython.display import display, Math
        prior_weights_mean = np.round(self.model.prior_weights_mean, 3)
        prior_weights_stdev = np.round(self.model.prior_weights_stdev, 3)
        prior_latents_mean = np.round(self.model.prior_latents_mean, 3)
        prior_latents_stdev = np.round(self.model.prior_latents_stdev, 3)
        likelihood_stdev = np.round(self.model.likelihood_stdev, 3)
        output_noise_stdev = np.round(self.model.output_noise_stdev, 3)
        s = "" if self.label is None else "\\textbf{{{} :}}\\\\".format(self.label)
        s += "W \\;\\sim\\; N(\\; {},\\; {}\\; ) \\\\".format( prior_weights_mean, prior_weights_stdev**2 )
        s += "Z \\;\\sim\\; N(\\; {},\\; {}\\; ) \\\\".format( prior_latents_mean, prior_latents_stdev**2 )
        s += "Y|W,Z \\;\\sim\\; N(\\; g_W(X),\\; {}\\; ) + N( 0, {} ) \\\\".format( likelihood_stdev**2, output_noise_stdev**2 )
        s += "W,Z|Y \\;\\sim\\; ? \\;\\rightarrow\\; \\text{{BNN LV}} \\\\".format()
        s = Math(s)
        display(s)

    def _repr_html_(self):
        self.display()

    def display(self):
        self.model.display()

    def _repr_html_(self):
        self.model._repr_html_()


class BNN:
    """
    A nerual network with M inputs and K outputs with D weights.
    The weights are represented as an S-by-D matrix,
    where D is the total number of weights in the network
    and S is typically 1 but can be an abitrary number of models
    (e.g. when doing a forward pass on a family of models 
    sampled from a posterion during Bayesian modeling).
    """

    def __init__(self, architecture, seed = None, weights = None):
        
        # Layer Assertions
        assert len(architecture['biases']) == len(architecture['activations']), "Error: Mismatch in layer dimensions - biases vs activations"
        assert (len(architecture['biases'])-1) == len(architecture['hidden_layers']), "Error: Mismatch in layer dimensions - must be 1 fewer hidden layer than biases/activations"
        for bias in architecture['biases']:
            assert bias == bool or bias == 1 or bias == 0, "Error: biases must be bool or int[0,1]"
        for act in architecture['activations']:
            assert act in ['relu', 'linear'], "Error: Only 'relu' and 'linear' activations have been implemented"

        # Combine output and hidden layers together to match N weight layers
        all_layers = architecture['hidden_layers'].copy()
        all_layers.append(architecture['output_n'])

        self.layers = {'input_n' : architecture['input_n'],
                       'output_n' : architecture['output_n'],
                       'hidden_layers_shape' : architecture['hidden_layers'],
                       'all_layers_shape' : all_layers,
                       'biases' : architecture['biases'],
                       'activations' : architecture['activations']}   
        self._D, self._layers_D = self._calculate_network_size()
        self.objective_trace = np.empty((1, 1))
        self.weight_trace = np.empty((1, self.D))
        
        self.seed = seed
        self.random = np.random.RandomState(seed)

        if weights is None:
            self.weights = self.random_weights()
        else:
            assert type(weights) == np.ndarray, "Error: Weights must be a numpy array"
            assert len(weights.shape) == 2, "Error: Weights must be specified as a 2D numpy array"
            assert weights.shape[1] == self.D, f"Error: Weight dimensions must match the shape specified in the architecture ((1,{self.D}))"
            self.weights = weights

    @property
    def M(self):
        """ Input dimensions. """
        return self.layers['input_n']

    @property
    def K(self):
        """ Output dimensions. """
        return self.layers['output_n']

    @property
    def D(self):
        """ Total number of weights. """
        return self._D

    @property
    def S(self):
        """ Number of different models for which the weights are stored. """
        return self.weights.shape[0]

    @property
    def H(self):
        """ Number of hidden layers (not counting input or output). """
        return len(self.layers['hidden_layers_shape'])

    def _calculate_network_size(self):
        '''
        Calculate the number of weights required to represent the specific architecture
        '''
        D = 0
        layers_D = []
        for i in range(len(self.layers['hidden_layers_shape'])):
            # First layer so use input nodes
            if i == 0:
                D += (self.layers['input_n'] * self.layers['hidden_layers_shape'][i])
            else:
                D += self.layers['hidden_layers_shape'][i-1] * self.layers['hidden_layers_shape'][i]
            if self.layers['biases'][i]:
                D += self.layers['hidden_layers_shape'][i]
            layers_D.append(D - int(np.sum(layers_D)))
        # Final output layer
        if len(self.layers['hidden_layers_shape'])>0:
            D += self.layers['hidden_layers_shape'][-1] * self.layers['output_n']
        else:  # Special case if there are no hidden layers:
            D += self.layers['input_n'] * self.layers['output_n']
        if self.layers['biases'][-1]:
            D += self.layers['output_n']
        layers_D.append(D - int(np.sum(layers_D)))

        return D, layers_D

    def random_weights(self, S=1):
        return self.random.normal(0, 1, size=(S, self.D))

    def stack_weights(self, W_layers):
        """
        Takes a list of (S-by-)IN-by-OUT tensors
        storing the weights for each layer in a model
        (or in each model from a set of S models)
        and returns an S-by-D matrix of the weights
        for the whole network (where S is 1 if there is only 1 model).
        IN and OUT are the number of input and output nodes
        for the given layer.
        """
        
        # Store results:
        W = []

        # Check numer of layers:
        n_layers = len(self.layers['all_layers_shape'])
        assert len(W_layers)==n_layers, f"Received {len(W_layers)} layers but expected {n_layers}."
        
        # Get dimensions:
        S = W_layers[0].shape[0] if len(W_layers[0].shape)==3 else 1
        
        # Loop through layers:
        for i,W_layer in enumerate(W_layers):
            
            # Get expected layer sizes:
            if i==0:
                source_size = self.layers['input_n']
            else:
                source_size = self.layers['all_layers_shape'][i-1]
            source_size += self.layers['biases'][i]
            target_size = self.layers['all_layers_shape'][i]
            
            # Check dimensions:
            if len(W_layer.shape)==2:
                W_layer = W_layer.reshape(1,*W_layer.shape)
            elif len(W_layer.shape)==3:
                assert W_layer.shape[0]==S, f"[layer {i+1}] Encounted set of {W_layer.shape[0]} weights but expected {S}."
            else:
                raise ValueError("W should be (S-by-)IN-by-OUT, i.e. (3 or) 2 dimenisions.")
            assert W_layer.shape[-2]==source_size, f"[layer {i+1}] Rows ({W_layer.shape[-2]}) should correspond to input nodes ({source_size})."
            assert W_layer.shape[-1]==target_size, f"[layer {i+1}] Columns ({W_layer.shape[-1]}) should correspond to output nodes ({target_size})."
            
            # Reshape and add to stack:
            W_layer = W_layer.reshape(S,source_size*target_size)
            W.append(W_layer)
        
        W = np.hstack(W)
        assert W.shape == (S,self.D), f"Found {W.shape[1]} weights but expected {self.D}."
        
        return W

    def unstack_weights(self, W):
        """
        Creates a list of the weights for each layer.
        W may be a row-vector of weights, or a matrix
        where each row corresponds to a different
        specification of the model (e.g. we may have S
        sets of weights, representing S different BNNs,
        given as a S-by-D matrix.)
        """
        
        if len(W.shape)==1:
            W = W.reshape(1,-1)
        elif len(W.shape)==2:
            assert W.shape[1] == self.D, f"Second dimension of W ({W.shape[1]}) must match number of weights ({self.D}); W.shape={W.shape} ."
        else:
            raise ValueError(f"W should be S-by-D or 1-by-D (i.e. max 2 dimenisions), not {W.shape}")
        
        # Determine how many sets of weights we have:
        S = W.shape[0]
            
        # Get sizes of layers:
        source_sizes = [self.layers['input_n']] + self.layers['all_layers_shape'][:-1]
        target_sizes = self.layers['all_layers_shape']
        for i,bias in enumerate(self.layers['biases']):
            source_sizes[i] += bias  # 0 or 1
            
        # Loop through layers:
        W_layers = []
        cursor = 0  # Keep track row of W.
        for source_size, target_size in zip(source_sizes,target_sizes):
            # Get the chunk of weights corresponding to this layer:
            W_layer = W[ :, cursor:(cursor+source_size*target_size) ]
            # Reshape the chunk to stack of matrices (i.e. a 3d tensor)
            # Where each matrix has rows corresponding to source nodes
            # and columns corresponding to target nodes:
            W_layer = W_layer.reshape(S, source_size, target_size)
            # Add tensor to list:
            W_layers.append(W_layer)
            # Update cursor:
            cursor += source_size*target_size
            
        return W_layers

    def set_weights(self, weights):
        '''
        Manually set the weights of the Neural Network
        '''
        if isinstance(weights, list):
            weights = self.stack_weights(weights)
        assert type(weights) == np.ndarray, "Error: Weights must be a numpy array"
        assert len(weights.shape) == 2, "Error: Weights must be specified as a 2D numpy array"
        assert weights.shape[1] == self.D, f"Error: Weight dimensions must match the shape specified in the architecture (num_weights={self.D})"
        self.weights = weights
        return

    def get_weights(self):
        '''
        Simple wrapper to return weights
        '''
        return self.weights

    @staticmethod
    def relu(x):
        return np.maximum(np.zeros(shape=x.shape), x)

    @staticmethod
    def identity(x):
        return x

    def fit(self, X, Y, step_size=0.01, max_iteration=5000, check_point=100, regularization_coef=None):
        '''

        '''
        # Check X dimensions:
        if len(X.shape) < 2:
            raise ValueError(f"X should be (at least) 2 dimensional; X.shape={X.shape}.")
        assert X.shape[-1]==self.M, f"Last dimenion of X is {X.shape[-1]} but should correspond to {self.M} inputs (i.e. features)"
        # Check Y dimensions:
        if len(Y.shape) < 2:
            raise ValueError(f"Y should be (at least) 2 dimensional; Y.shape={Y.shape}.")
        assert Y.shape[-1]==self.K, f"Last dimenion of Y is {Y.shape[-1]} but should correspond to {self.K} output"
        # Get number of "stacks" of datasets (i.e. the arbitrary dimensions before N and M,K):
        assert X.shape[:-1] ==  Y.shape[:-1], f"Besides the final dimension (M,K), the dimensions of X {X.shape} and Y {Y.shape} should match."
        N = X.shape[-2]  # Number of rows.
        R = X.shape[:-2]  # Arbitrary dimensions that precede the number of rows (N) and features (M).
        # Raise implementation error if there is more than a single 2D dataset:
        if len(R)>0:
            raise NotImplementedError(f"Current implementation does not support datasets of aritrary dimension, must be N-by-M; X.shape={X.shape}.")
        
        def objective(W, t):
            ''' Callbacks for each optimization step '''
            squared_error = np.linalg.norm(Y - self.forward(X, weights=W), axis=-1)**2
            if regularization_coef is None:
                mse = np.mean(squared_error, axis=-1)
                return mse
            else:
                mse = np.mean(squared_error, axis=-1) + regularization_coef * np.linalg.norm(W, axis=-1)
                return mse

        obj_gradient = grad(objective)

        def _call_back(weights, iteration, g):
            ''' Callbacks for each optimization step '''
            objective_val = objective(weights, iteration)
            self.objective_trace = np.vstack((self.objective_trace, objective_val))
            self.weight_trace = np.vstack((self.weight_trace, weights))
            if (check_point is not None) and (iteration % check_point == 0):
                print("Iteration {} lower bound {}; gradient mag: {}".format(iteration, objective_val, np.linalg.norm(obj_gradient(weights, iteration))))

    
        # Run the training method
        adam(obj_gradient, self.weights, step_size=step_size, num_iters=max_iteration, callback=_call_back)
        optimum_index = np.argmin(self.objective_trace[1:])
        self.weights = self.weight_trace[1:][optimum_index].reshape(1,-1)
        return

    def forward(self, X, weights=None):
        '''
        Perform a forward pass through the network from input to output.
        Requires the last dimension of X to be the number of inputs (i.e. features).
        X is generally expected by be an N-by-M matrix, but may in fact have
        an arbitrary dimensions instead of N (as long as M is the last dimension).
        The K outputs will be along the last dimension (with prior dimensions
        matching those of X, i.e. the typical output will be an N-by-K matrix).

        The current implementation requires either R=1 or R=S
        (i.e. if multiple datasets are provided, there must be a corresponding number of weights).
        This allows vectorization over S models.
        '''
        # Get weights:
        W = self.weights if weights is None else weights
        # Check W dimensions:
        assert len(W.shape)==2, f"W should be S by D matrix., not {W.shape}"
        # Check X dimensions:
        if len(X.shape) < 2:
            raise ValueError(f"X should be (at least) 2 dimensional; X.shape={X.shape}.")
        M = X.shape[-1]  # Number of features (final dimension).
        N = X.shape[-2]  # Number of rows (dimension before last).
        R = X.shape[:-2]  # Arbitrary dimensions that precede the number of rows (N) and features (M).
        assert X.shape[-1]==self.M, f"Last dimenion of X is {X.shape[-1]} but should correspond to {self.M} inputs (i.e. features)"
        # Raise implementation error if there is more than a single 2D dataset:
        if len(R)==0:
            R = 1
            X = X.reshape(1,*X.shape)  # Add R=1 as first demension to get 3 dimensions.
        elif len(R)==1:
            R = R[0]  # Get single value out of tuple.
        else:
            raise NotImplementedError(f"Current implementation does not support datasets of aritrary dimension, must be N-by-M; X.shape={X.shape}.")

        # Make there are the same number of sets (or 1) of weights and datasets:
        S = W.shape[0]
        assert (S==R) or (S==1) or (R==1), f"If either stack has more that 1 input, they must both has the same number -- incompatible shapes: {W.shape} and {X.shape}."
        # Use S to refer to larger stack size and ignore R:
        S = max(S,R)
        del R
        # Broadcast both inputs to have size S:
        if W.shape[0]<S:
            W = np.tile(W, reps=(S,1))  # Repeat S times along first axis and preserve other axis (D).
        if X.shape[0]<S:
            X = np.tile(X, reps=(S,1,1))  # Repeat S times along first axis and preserve other axes (N and M).
        
        # Get weights for each layer (as tensors):
        W_layers = self.unstack_weights(W=W)

        # Determine shape of output:
        Y_shape = tuple([S,*X.shape[1:-1], self.layers['output_n'] ])  # Determine shape of output.

        # Copy data to values to iterate through the network
        try:
            # Fails if `X` is a numpy autograd ArrayBox instead of a numpy ndarray:
            values_in = X.copy()
        except:
            # Skip copy if it fails:
            values_in = X

        # Loop through layers:
        #   Reminder: W_layer is an S-by-IN-by-OUT tensor of the weights for S models,
        #   with layer inputs on the rows and layer outputs on the columns.
        for i, weights in enumerate(W_layers):
            
            # If there is a bias, postpend a column of ones to each matrix:
            bias = self.layers['biases'][i]
            if bias==1:
                bias_features = np.ones((*values_in.shape[:-1],1))
                values_in = np.append(values_in,bias_features, axis=-1)

            # Calculate pre-activation values:
            values_pre = np.matmul( values_in, weights )

            # Apply activation fucntion:
            if self.layers['activations'][i] == 'relu':
                values_out = self.relu(values_pre)
            elif self.layers['activations'][i] == 'linear':
                values_out = self.identity(values_pre)
            else:
                raise ValueError(f"Error: Unexpected activation type - {self.layers['activations'][i]}")

            # Pass output values as input to next layer:
            values_in = values_out

        Y = values_out.reshape(Y_shape)

        # Special case: If input was 2D and there is only one set of weights
        # return a 2D output instead of 3D output with a first dimension of 1:
        if (S==1) and (len(Y.shape)==3) and (Y.shape[0]==1):
            S,N,K = Y.shape
            Y = Y.reshape(N,K)  # Drop the first dimension where S=1.
        
        return Y


class BNN_LV(BNN):
    """
    Implementation of Bayesian Neural Network with Latent Variables
    https://arxiv.org/pdf/1605.07127.pdf  Section 2.2.
    """

    def __init__(self, architecture, seed = None, weights = None):
        """
        Initialize a BNN with Latent Variable:
            Given an input X with N rows and M features,
            augment X by appeend L gaussian noise features (forming a modfied input X')
            and perturb Y by adding gaussian noise (forming a modified output Y').
            All noise has mean zero, and the standard devation is a hyperparameter:
            Each of the L latent variable inputs has its own standard deviation (gamma)
            and the noise on each of the K outputs has its own standard deviation (sigma).

        Uses the same architecture as the BNN superclass, but expects additional keys:
            gamma : list of L standard deviations for the latent variable inputs.
            sigma : list of K standard deviations for the additive output noises.
        """
        # Add a noise input.
        architecture = architecture.copy()
        assert 'input_n' in architecture.keys()  # Will be augmented by L below.
        # Get standard deviation of noise:
        if 'gamma' not in architecture:
            raise KeyError("Make sure achitecture includes 'gamma' (list of standard deviations for the L latent variable inputs).")
        self.gamma = architecture['gamma']  # List.
        if 'sigma' not in architecture:
            raise KeyError("Make sure achitecture includes 'sigma' (list of standard deviations for the K additive output noises).")
        self.sigma = architecture['sigma']  # List.
        # Check dimensions:
        self.gamma = np.array([self.gamma]).flatten()  # Coerce list to numpy array.
        self.sigma = np.array([self.sigma]).flatten()  # Coerce list to numpy array.
        if len(self.sigma) != architecture['output_n']:
            raise ValueError(f"The dimension of 'sigma' ({len(self.sigma)}) should match the dimension of the output ({architecture['output_n']}).")
        # Adjust input size by number of latent variables:
        self.L = len(self.gamma)
        architecture['input_n'] += self.L
        # Build a neural_network:
        super().__init__(architecture, seed=seed, weights=weights)
        # Keep track of latest noise variables:
        self.last_input_noise = None
        self.last_output_noise = None
        # Store addition state variables:
        self.fitting = False  # Flag for handing recursive calls to `fit` (generally False).
    
    def add_input_noise(self,X, input_noise='auto'):
        """
        Add a feature of input noise drawn from a Gaussian distribution
        with mean 0 and the standard deviation.
        X:
            The input to augment with latent features.
        input_noise:
            'auto' : Stochasticify is added automatically according to the BNN_LV's parameters.
            'zero' : No noise is added (i.e. adds columns of zeros instead of noise features).
            [tensor-like object] : Adds user-specified noise.
        """
        assert len(X.shape) in {2,3}, "X must have 2 or 3 dimensions."
        Z_shape = tuple((*X.shape[:-1],self.L))
        if isinstance(input_noise, str) and input_noise=='auto':
            Z = self.random.normal(loc=0, scale=self.gamma, size=Z_shape)
        elif isinstance(input_noise, str) and input_noise=='zero':
            Z = np.zeros(Z_shape)
        else:
            try:
                Z = input_noise
                if len(Z.shape)==2:
                    assert Z.shape == Z_shape
                elif len(Z.shape)==3:
                    assert Z.shape[1:] == Z_shape
                else:
                    raise ValueError
            except:
                wrong_shape = input_noise.shape if hasattr(input_noise, 'shape') else {type(input_noise)}
                raise ValueError(f"Expected a tensor-like object with shape {Z_shape} , not {wrong_shape}.")
        self.last_input_noise = Z  # Store last noise for access during training.
        # If either X or Z is 3 dimensional, tile them so both stacks are the same size:
        if len(X.shape)==3 or len(Z.shape)==3:
            # Make both 3 dimensional:
            if not len(X.shape)==3:
                X = X.reshape(1,*X.shape)
            if not len(Z.shape)==3:
                Z = Z.reshape(1,*Z.shape)
            # Get number of stacks:
            S = max(X.shape[0],Z.shape[0])
            assert X.shape[0] in {1,S}, f"If either X or Z is stacked, they must have the same stack size; cannot broadcast {X.shape} and {Z.shape}"
            assert Z.shape[0] in {1,S}, f"If either X or Z is stacked, they must have the same stack size; cannot broadcast {X.shape} and {Z.shape}"
            # Repeat one input if needed to get equal stacks:
            if X.shape[0]<S:
                X = np.tile(X, reps=(S,1,1))
            if Z.shape[0]<S:
                Z = np.tile(X, reps=(S,1,1))
        # Augment X with Z:
        X_ = np.concatenate([X,Z], axis=-1)
        return X_
    
    def add_output_noise(self,Y_, output_noise='auto'):
        """
        Corrupt output with additive noise drawn from a Gaussian distribution
        with mean 0 and a standard deviation specified for each dimension of the output.
        Y_:
            The output to perturb with additive noise.
        output_noise:
            'auto' : Stochasticify is added automatically according to the BNN_LV's samameters.
            'zero' : No noise is added (i.e. leaves the output unchanged).
            [tensor-like object] : Adds user-specified noise.
        """
        Eps_shape = Y_.shape
        if isinstance(output_noise, str) and output_noise=='auto':
            Eps = self.random.normal(loc=0, scale=self.sigma, size=Eps_shape)
        elif isinstance(output_noise, str) and output_noise=='zero':
            Eps = np.zeros(Eps_shape)
        else:
            try:
                Eps = output_noise
                if len(Eps.shape)==2:
                    assert Eps.shape == Eps_shape
                elif len(Eps.shape)==3:
                    assert Eps.shape[1:] == Eps_shape
                else:
                    raise ValueError
            except:
                wrong_shape = output_noise.shape if hasattr(output_noise, 'shape') else {type(output_noise)}
                raise ValueError(f"Expected a tensor-like object with shape {Eps_shape} , not {wrong_shape}.")
        self.last_output_noise = Eps  # Store last noise for access during training.
        Y = Y_ + Eps
        return Y
        
    def forward(self, X, weights=None, input_noise='auto', output_noise='auto'):
        """
        Perform a forward pass. Noise is added automatically unless specified by the user.
        input_noise:
            Parameter passed to `add_input_noise` (see that function for details).
        output_noise:
            Parameter passed to `add_output_noise` (see that function for details).
        """
        # Add input noise (extra feature):
        # Note: During gradient descent (i.e. when `fitting` flag is True),
        #       this step is skipped because noise was already added by `fit` method.
        if not self.fitting:
            X_ = self.add_input_noise(X, input_noise=input_noise)
        else:
            # During gradient descent (i.e. when `fitting` flag is True),
            # don't augment X because that was already handled by `fit` method.
            X_ = X

        # Perform forward pass through regular BNN:
        Y_ = super().forward(X_, weights=weights)

        # Add output noise (additive):
        if not self.fitting:
            Y = self.add_output_noise(Y_, output_noise=output_noise)
        else:
            # During gradient descent (i.e. when `fitting` flag is True),
            # don't augment Y because that was already handled by `fit` method.
            Y = Y_
        return Y

    def fit(self, X, Y, *args, **kwargs):
        """
        Fit the non-noisy verion of the neural net using gradient descent.
        (This is a non-bayesian approach, but useful for finding initialization weights).
        """
        # Prepare X and Y:
        X_ = self.add_input_noise(X, input_noise='zero')
        Y_ = self.add_output_noise(Y, output_noise='zero')

        self.fitting = True  # Put BNN LV in fit mode so that it stops adding columns to X.
        super().fit(X=X_, Y=Y_, *args, **kwargs)
        self.fitting = False  # Restore normal state.
        return

