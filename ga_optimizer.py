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

    def suggest_next(self, **kwargs):
        """
        Generate a new offspring using Selection, Crossover, and Mutation.
        """
        if len(self.population_x) < 2:
             # Fallback if suggest is called before enough data is collected
             return np.random.uniform(self.bounds[:, 0], self.bounds[:, 1], self.D)
             
        # 1. Selection: Tournament Selection
        # Pick 3 random individuals, choose the best as Parent 1
        idx1 = np.argmin([self.population_y[i] for i in np.random.choice(len(self.population_y), min(3, len(self.population_y)), replace=False)])
        parent1 = self.population_x[idx1]
        
        # Pick 3 random individuals, choose the best as Parent 2
        idx2 = np.argmin([self.population_y[i] for i in np.random.choice(len(self.population_y), min(3, len(self.population_y)), replace=False)])
        parent2 = self.population_x[idx2]
        
        # 2. Crossover: Arithmetic / Blend Crossover
        alpha = np.random.rand(self.D)
        offspring = alpha * parent1 + (1 - alpha) * parent2
        
        # 3. Mutation: Gaussian Mutation on random genes
        for i in range(self.D):
            if np.random.rand() < self.mutation_rate:
                scale = self.mutation_scale
                if i == 9: # CTLE has larger scale
                    scale *= 10.0
                offspring[i] += np.random.randn() * scale
                
        # Project back to bounds
        offspring = np.clip(offspring, self.bounds[:, 0], self.bounds[:, 1])
        
        # Enforce FFE L1 constraint (first 9 taps)
        if self.D >= 9:
            ffe_sum = np.sum(np.abs(offspring[:9]))
            offspring[:9] = offspring[:9] / max(ffe_sum, 1e-9)
            
        return offspring
