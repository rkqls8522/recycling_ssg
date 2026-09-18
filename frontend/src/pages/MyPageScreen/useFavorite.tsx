import { useState } from "react";
import useAxios from "@/hooks/useAxios";
import { FavoriteResponse } from "@/types";
import { authHeaders } from "@/utils/header";
import {
  CATEGORIES,
  MAJOR_CATEGORIES,
  getClassId,
} from "@/constants/wasteCategories";

export function useFavorite(
  refreshFavorites?: () => Promise<void>,
  existingClassIds: number[] = [],
) {
  const [items, setItems] = useState<SavedItem[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedMain, setSelectedMain] = useState("");
  const [selectedSub, setSelectedSub] = useState("");

  const mainCategories = MAJOR_CATEGORIES;
  const subCategories = selectedMain ? CATEGORIES[selectedMain] : [];

  const selectedClassId =
    selectedMain && selectedSub
      ? getClassId(selectedMain, selectedSub)
      : undefined;

  const alreadyRegistered =
    selectedClassId !== undefined &&
    existingClassIds.includes(selectedClassId);

  // 즐겨찾기 등록
  const { loading: addLoading, refetch: favoriteAddRequest } =
    useAxios<FavoriteResponse>("", { method: "post" }, false);

  async function handleAdd() {
    if (!selectedMain || !selectedSub) return;

    const class_id = getClassId(selectedMain, selectedSub);
    if (class_id === undefined) {
      console.error(
        `일치하는 class_id를 찾을 수 없습니다: ${selectedMain} / ${selectedSub}`,
      );
      return;
    }

    if (existingClassIds.includes(class_id)) {
      return;
    }

    if (!items.find((i) => i.main === selectedMain && i.sub === selectedSub)) {
      setItems((prev) => [...prev, { main: selectedMain, sub: selectedSub }]);
    }

    try {
      await favoriteAddRequest({
        url: "/api/v1/favorites",
        data: { class_id },
        headers: authHeaders(),
      });
      await refreshFavorites?.();
      setModalOpen(false);
      setSelectedMain("");
      setSelectedSub("");
    } catch (e) {
      console.log("즐겨찾기 등록 실패", e);
    }
  }

  // 즐겨찾기 삭제
  const { loading: deleteLoading, refetch: favoriteDeleteRequest } =
    useAxios<void>("", { method: "delete" }, false);

  function handleRemove(idx: number) {
    setItems((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleDelete(favorite_id: number) {
    try {
      await favoriteDeleteRequest({
        url: `/api/v1/favorites/${favorite_id}`,
        headers: authHeaders(),
      });
      refreshFavorites?.();
    } catch (e) {
      console.log("즐겨찾기 삭제 실패", e);
    }
  }

  function openModal() {
    setSelectedMain("");
    setSelectedSub("");
    setModalOpen(true);
  }

  return {
    handleAdd,
    handleRemove,
    handleDelete,
    deleteLoading,
    openModal,
    setModalOpen,
    mainCategories,
    subCategories,
    modalOpen,
    selectedMain,
    setSelectedMain,
    selectedSub,
    setSelectedSub,
    addLoading,
    alreadyRegistered,
  };
}

export const CATEGORY_EMOJI: Record<string, string> = {
  고철류: "🔩",
  나무: "🪵",
  도기류: "🏺",
  비닐: "🛍️",
  스티로폼: "📦",
  유리병: "🍾",
  의류: "👕",
  종이류: "📄",
  캔류: "🥤",
  페트병: "🍶",
  플라스틱류: "🧴",
  형광등: "💡",
};

export const CATEGORY_COLOR: Record<string, string> = {
  고철류: "bg-slate-100 text-slate-700",
  나무: "bg-amber-100 text-amber-700",
  도기류: "bg-orange-100 text-orange-700",
  비닐: "bg-purple-100 text-purple-700",
  스티로폼: "bg-orange-100 text-orange-700",
  유리병: "bg-cyan-100 text-cyan-700",
  의류: "bg-pink-100 text-pink-700",
  종이류: "bg-yellow-100 text-yellow-700",
  캔류: "bg-slate-100 text-slate-700",
  페트병: "bg-blue-100 text-blue-700",
  플라스틱류: "bg-blue-100 text-blue-700",
  형광등: "bg-green-100 text-green-700",
};

interface SavedItem {
  main: string;
  sub: string;
}
