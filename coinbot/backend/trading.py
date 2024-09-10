from abc import ABC, abstractmethod


class BaseTradingBot(ABC):
    def __init__(self):
        self.name = None
        self.initial_investment = None
        self.is_running = None
        self.exchange_client = None

    @abstractmethod
    def start(self, datagenerator):
        pass

    @abstractmethod
    def update(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    def buy(self, amount, symbol):
        raise NotImplementedError("The connection to the client is not yet implemented")

    def sell(self, amount, symbol):
        raise NotImplementedError("The connection to the client is not yet implemented")


class MomentumBot(BaseTradingBot):
    def __init__(self, initial_investment, symbol, short_moving_average, long_moving_average):
        super(MomentumBot).__init__()
        self.name = symbol + self.__class__.__name__
        self.initial_investment = initial_investment
        self.short_moving_average = short_moving_average
        self.long_moving_average = long_moving_average

    def start(self, datagenerator):
        pass

    def update(self):
        pass

    def stop(self):
        pass
