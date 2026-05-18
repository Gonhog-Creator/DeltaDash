import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';

export function useAuth() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data: user, isLoading, error } = useQuery({
    queryKey: ['currentUser'],
    queryFn: authApi.getCurrentUser,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });

  const loginMutation = useMutation({
    mutationFn: authApi.login,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['currentUser'] });
    },
  });

  const logoutMutation = useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      queryClient.setQueryData(['currentUser'], null);
      queryClient.removeQueries({ queryKey: ['currentUser'] });
      navigate('/login');
    },
  });

  const changePasswordMutation = useMutation({
    mutationFn: ({ oldPassword, newPassword }: { oldPassword: string; newPassword: string }) =>
      authApi.changePassword(oldPassword, newPassword),
  });

  return {
    user,
    isLoading,
    isAuthenticated: !!user,
    isAdmin: user?.is_admin || false,
    error,
    login: loginMutation.mutate,
    logout: logoutMutation.mutate,
    changePassword: changePasswordMutation.mutate,
    isLoggingIn: loginMutation.isPending,
    isLoggingOut: logoutMutation.isPending,
  };
}
