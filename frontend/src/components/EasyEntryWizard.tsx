import { useState } from 'react';
import { X, ChevronLeft, Check } from 'lucide-react';

type WizardField = 'sessionName' | 'labName' | 'protocol' | 'geometryId' | 'protectionLevel' | 'isOfficial';
type Step = 'name' | 'lab' | 'protocol' | 'geometry' | 'protection' | 'official';

interface EasyEntryWizardProps {
  sessionName: string;
  labName: string;
  protocol: string;
  geometryId: string;
  protectionLevel: string;
  isOfficial: boolean;
  locations?: { id: string; name: string }[];
  protocols?: { id: string; name: string }[];
  geometries?: { id: string; name: string }[];
  protectionLevelOptions: string[];
  onSelect: (field: WizardField, value: string) => void;
  onClose: () => void;
}

const STEP_TITLES: Record<Step, string> = {
  name: 'Session Name',
  lab: 'Lab / Location',
  protocol: 'Protocol',
  geometry: 'Geometry',
  protection: 'Protection Level',
  official: 'Official Certification?',
};

/**
 * Step-by-step session setup wizard: each field is presented one at a time as
 * large tap-friendly buttons (or a text box for the name) instead of dropdowns.
 */
export function EasyEntryWizard({
  sessionName,
  labName,
  protocol,
  geometryId,
  protectionLevel,
  isOfficial,
  locations,
  protocols,
  geometries,
  protectionLevelOptions,
  onSelect,
  onClose,
}: EasyEntryWizardProps) {
  const [stepIndex, setStepIndex] = useState(0);
  const [nameDraft, setNameDraft] = useState(sessionName);

  // Protection level only applies when the selected protocol defines levels
  const steps: Step[] = ['name', 'lab', 'protocol', 'geometry'];
  if (protectionLevelOptions.length > 0) steps.push('protection');
  steps.push('official');

  const step = steps[Math.min(stepIndex, steps.length - 1)];

  const advance = () => {
    if (stepIndex + 1 >= steps.length) onClose();
    else setStepIndex(stepIndex + 1);
  };

  const pick = (field: WizardField, value: string) => {
    onSelect(field, value);
    advance();
  };

  const optionButton = (key: string, label: string, selected: boolean, onClick: () => void) => (
    <button
      key={key}
      onClick={onClick}
      className={`w-full flex items-center justify-between px-4 py-3.5 rounded-xl border-2 text-left text-base font-medium transition-colors ${
        selected
          ? 'border-blue-500 bg-blue-50 text-blue-900'
          : 'border-gray-200 text-gray-800 hover:border-blue-300 hover:bg-gray-50 active:bg-gray-100'
      }`}
    >
      <span className="truncate">{label}</span>
      {selected && <Check size={18} className="text-blue-600 shrink-0 ml-2" />}
    </button>
  );

  const optionList = (options: { key: string; label: string; selected: boolean; onClick: () => void }[]) => (
    <div className="flex-1 overflow-y-auto space-y-2 pr-1">
      {options.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-6">No options available.</p>
      ) : (
        options.map((o) => optionButton(o.key, o.label, o.selected, o.onClick))
      )}
    </div>
  );

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-gray-900/60 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">{STEP_TITLES[step]}</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Step {Math.min(stepIndex, steps.length - 1) + 1} of {steps.length}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Step content */}
        <div className="flex-1 overflow-hidden flex flex-col px-5 py-4">
          {step === 'name' && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                onSelect('sessionName', nameDraft.trim());
                advance();
              }}
              className="flex flex-col gap-3"
            >
              <input
                type="text"
                autoFocus
                value={nameDraft}
                onChange={(e) => setNameDraft(e.target.value)}
                placeholder="e.g. NIJ Test - Batch 2024-01"
                className="w-full px-4 py-3 text-base border-2 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none"
              />
              <button
                type="submit"
                className="w-full px-4 py-3.5 text-base font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-xl transition-colors"
              >
                Continue
              </button>
            </form>
          )}

          {step === 'lab' &&
            optionList(
              (locations ?? []).map((loc) => ({
                key: loc.id,
                label: loc.name,
                selected: labName === loc.name,
                onClick: () => pick('labName', loc.name),
              }))
            )}

          {step === 'protocol' &&
            optionList(
              (protocols ?? []).map((p) => ({
                key: p.id,
                label: p.name,
                selected: protocol === p.name,
                onClick: () => pick('protocol', p.name),
              }))
            )}

          {step === 'geometry' &&
            optionList(
              (geometries ?? []).map((g) => ({
                key: g.id,
                label: g.name,
                selected: geometryId === g.id,
                onClick: () => pick('geometryId', g.id),
              }))
            )}

          {step === 'protection' &&
            optionList(
              protectionLevelOptions.map((lvl) => ({
                key: lvl,
                label: lvl,
                selected: protectionLevel === lvl,
                onClick: () => pick('protectionLevel', lvl),
              }))
            )}

          {step === 'official' && (
            <div className="flex-1 flex flex-col justify-center gap-3">
              {optionButton('yes', 'Yes', isOfficial, () => pick('isOfficial', 'true'))}
              {optionButton('no', 'No', !isOfficial, () => pick('isOfficial', 'false'))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-gray-200">
          {stepIndex > 0 ? (
            <button
              onClick={() => setStepIndex(stepIndex - 1)}
              className="flex items-center gap-1 px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ChevronLeft size={16} />
              Back
            </button>
          ) : (
            <span />
          )}
          {step !== 'name' && (
            <button
              onClick={advance}
              className="px-3 py-2 text-sm font-medium text-gray-500 hover:bg-gray-100 rounded-lg transition-colors"
            >
              Skip
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
