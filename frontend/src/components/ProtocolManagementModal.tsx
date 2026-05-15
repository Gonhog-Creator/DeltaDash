import { ConfirmModal } from './ConfirmModal';

interface Protocol {
  id: string;
  name: string;
  description?: string;
}

interface ProtocolManagementModalProps {
  isOpen: boolean;
  protocols: Protocol[];
  newProtocolName: string;
  newProtocolDescription: string;
  onNameChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onEdit: (protocol: Protocol) => void;
  onDelete: (protocolId: string) => void;
  onAdd: () => void;
  onCancel: () => void;
}

export function ProtocolManagementModal({
  isOpen,
  protocols,
  newProtocolName,
  newProtocolDescription,
  onNameChange,
  onDescriptionChange,
  onEdit,
  onDelete,
  onAdd,
  onCancel,
}: ProtocolManagementModalProps) {
  if (!isOpen) return null;

  return (
    <ConfirmModal
      title="Manage Protocols"
      message={
        <div className="space-y-4">
          <div className="space-y-2">
            <h3 className="font-medium text-gray-900">Existing Protocols</h3>
            {protocols && protocols.length > 0 ? (
              <ul className="space-y-2">
                {protocols.map((prot) => (
                  <li key={prot.id} className="flex justify-between items-center text-sm text-gray-600">
                    <span>{prot.name} {prot.description && `(${prot.description})`}</span>
                    <div className="flex gap-2">
                      <button
                        onClick={() => onEdit(prot)}
                        className="text-blue-600 hover:text-blue-900"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => onDelete(prot.id)}
                        className="text-red-600 hover:text-red-900"
                      >
                        Delete
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-gray-500">No protocols created yet</p>
            )}
          </div>
          <div className="pt-4 border-t">
            <h3 className="font-medium text-gray-900 mb-2">Add New Protocol</h3>
            <input
              type="text"
              value={newProtocolName}
              onChange={(e) => onNameChange(e.target.value)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border mb-2"
              placeholder="Protocol name"
            />
            <input
              type="text"
              value={newProtocolDescription}
              onChange={(e) => onDescriptionChange(e.target.value)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
              placeholder="Description (optional)"
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
