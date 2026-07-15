import numpy as np

class GeneticAlgorithmOptimizer:
    def __init__(self, bounds, pop_size=10, mutation_rate=0.2, mutation_scale=0.1):
        """
        White-box implementation of a Continuous Genetic Algorithm (Real-coded GA).
        It maintains a population, and generates new offspring via crossover and mutation.
        """
        self.bounds = np.array(bounds)
        self.D = len(bounds)
        self.pop_size = pop_size
        self.mutation_rate = mutation_rate
        self.mutation_scale = mutation_scale
        
        self.population_x = []
        self.population_y = []

    def fit(self, X_data, y_data):
        """
        Update the population with the evaluated history.
        We take the top `pop_size` individuals as our current generation.
        """
        if len(X_data) == 0:
            return
            
        # Get unique evaluated points to avoid population collapse into identical clones
        unique_points = {}
        for x, y in zip(X_data, y_data):
            # Use string representation of rounded array as hash key to filter near-duplicates
            key = str(np.round(x, 3).tolist())
            if key not in unique_points or y < unique_points[key][1]:
                unique_points[key] = (x, y)
                
        # Sort all unique points by objective (y) ascending
        sorted_unique = sorted(unique_points.values(), key=lambda item: item[1])
        
        # Select top `pop_size` to form the population
        top_k = sorted_unique[:self.pop_size]
        self.population_x = [item[0] for item in top_k]
        self.population_y = [item[1] for item in top_k]

    def suggest_next(self, X_data=None, **kwargs):
        """
        Generate a new offspring using Elitism, Crossover, and Mutation.
        """
        if len(self.population_x) < 2:
             # Initialize population locally around the first known point if available
             if X_data is not None and len(X_data) > 0:
                 base_point = X_data[0]
             else:
                 base_point = np.zeros(self.D)
             new_ind = base_point + np.random.randn(self.D) * 0.05
             return np.clip(new_ind, self.bounds[:, 0], self.bounds[:, 1])
             
        # 1. Elitism: Inject the absolute best individual periodically
        # Since suggest_next generates one individual at a time, we keep a counter
        if not hasattr(self, 'eval_counter'):
            self.eval_counter = 0
            
        self.eval_counter += 1
        
        # Every 'pop_size' evaluations, we simply return the elite (best so far) to ensure it's not lost
        if self.eval_counter % self.pop_size == 0:
            best_idx = np.argmin(self.population_y)
            return self.population_x[best_idx].copy()
             
        # 2. Selection: Tournament Selection
        # Pick 3 random individuals, choose the best as Parent 1
        idx1 = np.argmin([self.population_y[i] for i in np.random.choice(len(self.population_y), min(3, len(self.population_y)), replace=False)])
        parent1 = self.population_x[idx1]
        
        # Pick 3 random individuals, choose the best as Parent 2
        idx2 = np.argmin([self.population_y[i] for i in np.random.choice(len(self.population_y), min(3, len(self.population_y)), replace=False)])
        parent2 = self.population_x[idx2]
        
        # 3. Crossover: BLX-alpha Crossover
        alpha = 0.5
        offspring = np.zeros(self.D)
        for i in range(self.D):
            c_min = min(parent1[i], parent2[i])
            c_max = max(parent1[i], parent2[i])
            span = c_max - c_min
            # Sample uniformly from [c_min - alpha*span, c_max + alpha*span]
            offspring[i] = np.random.uniform(c_min - alpha * span, c_max + alpha * span)
        
        # 4. Mutation: Polynomial/Gaussian Mutation with P_m = 1/D
        mutation_prob = 1.0 / self.D
        for i in range(self.D):
            if np.random.rand() < mutation_prob:
                scale = self.mutation_scale
                if i == self.D - 1: # CTLE has larger scale
                    scale *= 10.0
                offspring[i] += np.random.randn() * scale
                
        # Project back to bounds
        offspring = np.clip(offspring, self.bounds[:, 0], self.bounds[:, 1])
        
        return offspring
