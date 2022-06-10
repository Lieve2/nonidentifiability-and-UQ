## Welcome to the project code of "Unreliable Uncertainty: How Bayesian Non-identifiability Influences the Performance of Uncertainty Quantification Methods in the Context of Reinforcement Learning"

### Author
Lieve Göbbels

### Purpose 

This project code is part of the BEP written for the Bachelor Data Science at TU/e.


### Important components of the repo include:

#### Examples
Experiments on two (simplified, 2D) reinforcement learning benchmarks
- Wet-chicken
- Lunar-lander v2

Each experiment (on each benchmark) is done with five different sampling (uncertainty quantification) models from the pymc3 library,
namely HMC, NUTS, Metropolis, ADVI, and SVGD. The (main) results of the experiments can be found in the two notebooks [here](https://github.com/Lieve2/nonidentifiability-and-UQ/blob/master/notebooks/chicken_results.ipynb) (Wet-chicken) and [here](https://github.com/Lieve2/nonidentifiability-and-UQ/blob/master/notebooks/lunar_results.ipynb) (Lunar-lander). 


#### Implementations of Bayesian models.
This code can be found in the utils folder.
For neural networks, the dimensions are described as follows, unless otherwise noted:
- Input X, generally an N (rows) by M (features) data set.
- Output Y, generally an N-by-K matrix for a K-output model.
- Weights W of a single neural network are stored
  as a 1-by-D matrix for a network with D weights.
  When representing the weights of a set of S models, the weights
  are stored in an S-by-D matrix. 
- Latent features L of Gaussian noise
  are appeneded to the input X to form an augmented input X' in the latent variable model.
- Gaussian noise is added to each of the output Y
  to form a pertured output Y'.


## General setup:

The section for it is for anyone interested in running our code.

After Fork in the repo to your local machine, follow these steps to install the Pipenv used in developing this library.

To setup the env:  
`pip install pipenv`  
`pipenv install --dev`

To install new packages:  
`pipenv install ... # some package`

To run tests:  
`pipenv run pytest`  
or  
`pipenv shell`  
`pytest`  

To enter the shell:  
`pipenv shell`  

To leave the shell:
`exit`  
