import { useCallback, useEffect, useRef, useState } from "react";
import { getMyApprovedScopusIdentities, getMyLecturerProfile } from "../../api/lecturerScopus";
import type { ApprovedScopusIdentity, LecturerScopusProfile } from "../../types/lecturerScopus";

export default function useProfileData() {
  const [profile, setProfile] = useState<LecturerScopusProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [identities, setIdentities] = useState<ApprovedScopusIdentity[]>([]);
  const [identitiesLoading, setIdentitiesLoading] = useState(true);
  const [identitiesError, setIdentitiesError] = useState<unknown>(null);
  const profileController = useRef<AbortController | null>(null);
  const identitiesController = useRef<AbortController | null>(null);

  const loadProfile = useCallback(() => {
    profileController.current?.abort();
    const controller = new AbortController();
    profileController.current = controller;
    setLoading(true);
    setProfile(null);
    setError(null);
    void getMyLecturerProfile({ signal: controller.signal })
      .then((data) => { if (!controller.signal.aborted) setProfile(data); })
      .catch((requestError: unknown) => { if (!controller.signal.aborted) setError(requestError); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
  }, []);

  const loadIdentities = useCallback(() => {
    identitiesController.current?.abort();
    const controller = new AbortController();
    identitiesController.current = controller;
    setIdentitiesLoading(true);
    setIdentities([]);
    setIdentitiesError(null);
    void getMyApprovedScopusIdentities({ signal: controller.signal })
      .then((data) => { if (!controller.signal.aborted) setIdentities(data); })
      .catch((requestError: unknown) => { if (!controller.signal.aborted) setIdentitiesError(requestError); })
      .finally(() => { if (!controller.signal.aborted) setIdentitiesLoading(false); });
  }, []);

  useEffect(() => {
    loadProfile();
    loadIdentities();
    return () => {
      profileController.current?.abort();
      identitiesController.current?.abort();
    };
  }, [loadProfile, loadIdentities]);

  return { profile, loading, error, identities, identitiesLoading, identitiesError, loadProfile, loadIdentities, applyProfile: setProfile };
}
