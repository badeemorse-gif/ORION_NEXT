from bootstrap.bootstrap_registry import BootstrapRegistry

class BootstrapService:
    """
    Bootstrap Service
    Responsibility: Execute the registered builders in the startup sequence.
    """
    def __init__(self, registry: BootstrapRegistry) -> None:
        # The service now receives the populated registry via dependency injection
        self.registry = registry

    def execute_bootstrap(self) -> dict:
        """
        Executes all builders currently held in the registry.
        The service does not know the identity of these builders.
        """
        builders = self.registry.get_all_builders()
        bootstrap_result = {}
        
        for key, builder in builders.items():
            bootstrap_result[key] = builder.bootstrap()
            
        return bootstrap_result