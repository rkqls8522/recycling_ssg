import { useState, useEffect, useCallback, useRef } from "react";
import axios, { AxiosError, AxiosRequestConfig } from "axios";

interface UseAxiosState<T> {
  data: T | null;
  error: AxiosError | null;
  loading: boolean;
}

interface UseAxiosReturn<T> extends UseAxiosState<T> {
  refetch: (overrideOptions?: AxiosRequestConfig) => Promise<T>;
}

/**
 * useAxios - axios 요청을 위한 커스텀 훅
 * @param url - 요청할 URL
 * @param options - axios config (method, params, data, headers 등)
 * @param immediate - true면 마운트 시 자동 요청 (기본값: true)
 */
function useAxios<T = unknown>(
  url: string,
  options: AxiosRequestConfig = {},
  immediate: boolean = true,
): UseAxiosReturn<T> {
  const [state, setState] = useState<UseAxiosState<T>>({
    data: null,
    error: null,
    loading: immediate,
  });

  // options가 매 렌더마다 새 객체로 들어와도 무한루프 안 나게 ref로 고정
  const optionsRef = useRef<AxiosRequestConfig>(options);
  optionsRef.current = options;

  const fetchData = useCallback(
    async (overrideOptions: AxiosRequestConfig = {}): Promise<T> => {
      const controller = new AbortController();
      setState((prev) => ({ ...prev, loading: true, error: null }));

      try {
        const response = await axios<T>({
          url,
          signal: controller.signal,
          ...optionsRef.current,
          ...overrideOptions,
        });
        setState({ data: response.data, error: null, loading: false });
        return response.data;
      } catch (err) {
        if (!axios.isCancel(err)) {
          setState((prev) => ({
            ...prev,
            error: err as AxiosError,
            loading: false,
          }));
        }
        throw err;
      }
    },
    [url],
  );

  useEffect(() => {
    const controller = new AbortController();

    if (immediate) {
      setState((prev) => ({ ...prev, loading: true, error: null }));

      axios<T>({
        url,
        signal: controller.signal,
        ...optionsRef.current,
      })
        .then((response) => {
          setState({ data: response.data, error: null, loading: false });
        })
        .catch((err) => {
          if (!axios.isCancel(err)) {
            setState((prev) => ({
              ...prev,
              error: err as AxiosError,
              loading: false,
            }));
          }
        });
    }

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, immediate]);

  return { ...state, refetch: fetchData };
}

export default useAxios;
