import React from 'react';

const MetricCard: React.FC<{ name: string; what: string; good: string; caveat?: string }> = ({ name, what, good, caveat }) => (
  <div className="border border-gray-200 rounded-lg p-4">
    <h3 className="font-semibold text-indigo-700">{name}</h3>
    <p className="text-sm text-gray-700 mt-1">{what}</p>
    <p className="text-sm text-gray-500 mt-1"><span className="font-medium">Interpretation:</span> {good}</p>
    {caveat && <p className="text-xs text-amber-700 mt-1">{caveat}</p>}
  </div>
);

export const MetricsGuideTab: React.FC = () => {
  return (
    <div className="space-y-6 max-w-4xl">
      {/* How evaluation works */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-3">How the Model Is Evaluated</h2>
        <p className="text-sm text-gray-700">
          When the model trains, part of the data is <strong>held out</strong> — the model never sees it
          during training, then is scored on how well it predicts that hidden data. This is the honest
          estimate of real-world performance.
        </p>
        <p className="text-sm text-gray-700 mt-2">
          Ours is a <strong>grouped holdout</strong>: entire <em>vests</em> are held out, not random shots.
          If we held out random shots, the model could "cheat" by memorizing the vest a shot came from.
          Holding out whole vests simulates what happens when a new vest design arrives.
        </p>
        <div className="mt-4 bg-amber-50 border border-amber-200 rounded p-3 text-sm text-amber-800">
          <strong>In-sample vs holdout:</strong> "in-sample" numbers score the model on the same data it
          trained on — like quizzing a student on the practice exam. They always look optimistically good
          and should never be quoted as real-world accuracy. The held-out vest metrics are the honest ones.
        </div>
      </div>

      {/* BFD regression metrics */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-3">Backface Deformation Metrics</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <MetricCard
            name="MAE — Mean Absolute Error"
            what="On average, how many millimeters off is the predicted backface deformation? The headline number."
            good="Lower is better. ~5mm MAE against BFDs that range 15–45mm is usable but not tight."
          />
          <MetricCard
            name="MAPE — Mean Absolute % Error"
            what="The same error expressed as a percentage of the true value."
            good="Lower is better."
            caveat="Looks worse than it is: a 2mm miss on a small 8mm BFD is already 25% error. Don't lead with this number."
          />
          <MetricCard
            name="Bias — Mean Residual"
            what="The average direction of error: does the model systematically over- or under-predict?"
            good="Near zero is ideal. A positive value means we predict slightly more deformation than measured — mildly conservative, the safer direction for armor assessment."
          />
          <MetricCard
            name="Residual Sigma (σ)"
            what="The spread of errors — how consistent the predictions are."
            good="Smaller is better. ~7mm means most predictions land within ±7mm of truth. This feeds the uncertainty bands in Risk Analytics."
          />
          <MetricCard
            name="r — Correlation"
            what="Does the model get the ordering right? If one vest really deforms more than another, does the model rank it higher?"
            good="Closer to 1.0 is better. ~0.75 means vest comparisons are usually right even when exact mm values are off — this matters most for 'which design is better' questions."
          />
          <MetricCard
            name="5-Fold Cross-Validation"
            what="Instead of one holdout split, we train 5 times — each time hiding a different fifth of the vests — and average the results."
            good="Reported as mean ± std (e.g. 4.6 ± 0.8mm). More stable than a single holdout and the best single number to quote."
          />
        </div>
      </div>

      {/* Classifier metrics */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-3">Perforation Classifier Metrics</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <MetricCard
            name="AUC — Area Under Curve"
            what="Does the model rank perforations above stops? 0.5 = coin flip, 1.0 = perfect separation."
            good="Above 0.8 is good. Currently not computable — no perforated vests in the holdout yet."
          />
          <MetricCard
            name="Brier Score"
            what="How accurate the probability estimates themselves are (0 = perfect, lower is better)."
            good="Also blocked until real perforation outcomes exist in validation data."
          />
        </div>
        <div className="mt-4 bg-blue-50 border border-blue-200 rounded p-3 text-sm text-blue-800">
          <strong>"Exploratory" label:</strong> shown next to perforation predictions when there isn't enough
          real validation data behind them. Direction (thin vs thick) is trustworthy; the exact percentage
          isn't calibrated yet. It upgrades automatically once real perforation outcomes enter the data.
        </div>
      </div>

      {/* Anchors */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-3">Anchor Points</h2>
        <p className="text-sm text-gray-700">
          Anchor points are authored or physics-generated shots placed at known boundary conditions
          (e.g. "this armor definitely stops 9mm"). They train the model where real data is thin —
          especially at the thin end of the layer spectrum, which has almost no real shots.
        </p>
        <p className="text-sm text-gray-700 mt-2">
          <strong>Anchor Point Average Error</strong> scores how well the model reproduces those known
          boundary conditions — it's evaluated separately from real shots so the two numbers stay honest.
        </p>
      </div>

      {/* One-liner */}
      <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-5">
        <h2 className="text-lg font-semibold text-indigo-800 mb-2">The One-Liner</h2>
        <p className="text-sm text-indigo-900 italic">
          "We hold out entire vests the model has never seen; on those, it predicts backface deformation
          within roughly 5mm on average, ranks vest designs correctly most of the time, and flags
          thin-vs-thick perforation risk correctly — though the exact perforation percentage is still
          marked exploratory until we have real failure data."
        </p>
      </div>
    </div>
  );
};
