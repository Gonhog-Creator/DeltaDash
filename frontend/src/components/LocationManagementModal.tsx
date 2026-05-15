import { ConfirmModal } from './ConfirmModal';

interface Location {
  id: string;
  name: string;
  address?: string;
}

interface LocationManagementModalProps {
  isOpen: boolean;
  locations: Location[];
  newLocationName: string;
  newLocationAddress: string;
  onNameChange: (value: string) => void;
  onAddressChange: (value: string) => void;
  onEdit: (location: Location) => void;
  onDelete: (locationId: string) => void;
  onAdd: () => void;
  onCancel: () => void;
}

export function LocationManagementModal({
  isOpen,
  locations,
  newLocationName,
  newLocationAddress,
  onNameChange,
  onAddressChange,
  onEdit,
  onDelete,
  onAdd,
  onCancel,
}: LocationManagementModalProps) {
  if (!isOpen) return null;

  return (
    <ConfirmModal
      title="Manage Labs"
      message={
        <div className="space-y-4">
          <div className="space-y-2">
            <h3 className="font-medium text-gray-900">Existing Labs</h3>
            {locations && locations.length > 0 ? (
              <ul className="space-y-2">
                {locations.map((loc) => (
                  <li key={loc.id} className="flex justify-between items-center text-sm text-gray-600">
                    <span>{loc.name} {loc.address && `(${loc.address})`}</span>
                    <div className="flex gap-2">
                      <button
                        onClick={() => onEdit(loc)}
                        className="text-blue-600 hover:text-blue-900"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => onDelete(loc.id)}
                        className="text-red-600 hover:text-red-900"
                      >
                        Delete
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-gray-500">No labs created yet</p>
            )}
          </div>
          <div className="pt-4 border-t">
            <h3 className="font-medium text-gray-900 mb-2">Add New Lab</h3>
            <input
              type="text"
              value={newLocationName}
              onChange={(e) => onNameChange(e.target.value)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border mb-2"
              placeholder="Lab name"
            />
            <input
              type="text"
              value={newLocationAddress}
              onChange={(e) => onAddressChange(e.target.value)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
              placeholder="Address (optional)"
            />
          </div>
        </div>
      }
      confirmLabel="Add"
      variant="default"
      onConfirm={onAdd}
      onCancel={onCancel}
    />
  );
}
