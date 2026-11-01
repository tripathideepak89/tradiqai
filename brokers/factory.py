"""Broker factory - instantiate the correct broker adapter"""
from typing import Dict, Any
from brokers.base import BaseBroker
from brokers.groww import GrowwBroker


class BrokerFactory:
    """Factory to create broker instances"""

    @staticmethod
    def create_broker(broker_name: str, config: Dict[str, Any]) -> BaseBroker:
        """Create and return a broker instance

        Args:
            broker_name: Name of the broker (only "groww" is supported)
            config: Configuration dictionary for the broker

        Returns:
            BaseBroker instance

        Raises:
            ValueError: If broker name is not supported
        """
        broker_name = broker_name.lower()

        if broker_name == "groww":
            return GrowwBroker(config)
        else:
            raise ValueError(f"Unsupported broker: {broker_name} (only 'groww' is supported)")
