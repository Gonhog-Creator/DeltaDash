interface LoadingOverlayProps {
  message?: string;
  submessage?: string;
}

export function LoadingOverlay({ message = 'Loading...', submessage }: LoadingOverlayProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" />
      <div className="relative bg-white rounded-lg shadow-xl w-full max-w-sm mx-4 p-8 flex flex-col items-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-gray-200 border-t-blue-600 mb-4" />
        <p className="text-lg font-semibold text-gray-900">{message}</p>
        {submessage && (
          <p className="text-sm text-gray-500 mt-1 text-center">{submessage}</p>
        )}
      </div>
    </div>
  );
}
