"""GARCH(1,1) engine: fit with ``arch``, simulation vectorized with NumPy."""

import math

import numpy as np
from arch import arch_model

from finbrain_server.application.ports import GarchEngine
from finbrain_server.domain.entities import GarchParameters
from finbrain_server.domain.exceptions import SimulationError

MAX_DAILY_RETURN_PERCENT = 50.0


class ArchGarchEngine(GarchEngine):
    """Fits GARCH(1,1) by maximum likelihood and simulates many paths.

    The fit uses a constant mean, GARCH(1,1) volatility and normal
    errors (``arch.arch_model``). The simulation runs the variance
    recursion for every path at once, which is much faster than one
    ``arch`` simulation per path, and starts from the last conditional
    variance of the fit when it is known.
    """

    def fit(self, returns_percent: list[float]) -> GarchParameters:
        """Estimate the model by maximum likelihood.

        Parameters
        ----------
        returns_percent : list[float]
            Daily returns in percent (1.0 = 1%).

        Returns
        -------
        GarchParameters
            Fitted parameters with the last conditional variance.

        Raises
        ------
        SimulationError
            When the optimizer fails or the fit is not stationary.
        """
        data = np.asarray(returns_percent, dtype=float)
        data = data[np.isfinite(data)]
        try:
            result = arch_model(
                data, mean="Constant", vol="GARCH", p=1, q=1, dist="normal"
            ).fit(disp="off", show_warning=False)
        except Exception as error:
            raise SimulationError(f"The GARCH fit failed: {error}") from error
        params = result.params
        parameters = GarchParameters(
            mu=float(params["mu"]),
            omega=float(params["omega"]),
            alpha=float(params["alpha[1]"]),
            beta=float(params["beta[1]"]),
            last_variance=float(result.conditional_volatility[-1]) ** 2,
            last_residual=float(result.resid[-1]),
        )
        if not all(
            math.isfinite(value)
            for value in (parameters.mu, parameters.omega, parameters.alpha, parameters.beta)
        ) or parameters.persistence >= 1:
            raise SimulationError(
                "The fitted GARCH model is not stationary (alpha + beta >= 1)."
            )
        return parameters

    def simulate_returns(
        self,
        parameters: GarchParameters,
        n_days: int,
        n_paths: int,
        seed: int | None,
    ) -> list[list[float]]:
        """Simulate daily returns in percent.

        Parameters
        ----------
        parameters : GarchParameters
            Model to simulate.
        n_days : int
            Days per path.
        n_paths : int
            Number of independent paths.
        seed : int | None
            Seed of the random generator, for reproducible results.

        Returns
        -------
        list[list[float]]
            ``n_paths`` lists of ``n_days`` returns, each clipped to
            +/- 50% a day.

        Example
        -------
        >>> engine = ArchGarchEngine()
        >>> model = GarchParameters(mu=0.05, omega=0.02, alpha=0.1, beta=0.85)
        >>> paths = engine.simulate_returns(model, 10, 3, seed=1)
        >>> len(paths), len(paths[0])
        (3, 10)
        """
        generator = np.random.default_rng(seed)
        shocks = generator.standard_normal((n_paths, n_days))
        if parameters.last_variance is not None and parameters.last_residual is not None:
            variance = np.full(
                n_paths,
                parameters.omega
                + parameters.alpha * parameters.last_residual**2
                + parameters.beta * parameters.last_variance,
            )
        else:
            variance = np.full(n_paths, parameters.long_run_variance)
        returns = np.empty((n_paths, n_days))
        for day in range(n_days):
            residual = np.sqrt(variance) * shocks[:, day]
            returns[:, day] = parameters.mu + residual
            variance = (
                parameters.omega
                + parameters.alpha * residual**2
                + parameters.beta * variance
            )
        np.clip(returns, -MAX_DAILY_RETURN_PERCENT, MAX_DAILY_RETURN_PERCENT, out=returns)
        return returns.tolist()
