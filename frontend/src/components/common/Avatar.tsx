import { useState } from "react";

interface AvatarProps {
  /** Google profile picture URL, or null/undefined for the initials placeholder. */
  src?: string | null;
  /** Name the initial is drawn from, and the image's alt text. */
  name: string;
  /** Sizing + shape classes shared by both the image and the placeholder circle. */
  className?: string;
}

/**
 * Google avatars need `referrerPolicy="no-referrer"` — Google's image CDN
 * otherwise rejects the request for some referrer values — and a graceful
 * fallback to the initials circle if the URL 404s (e.g. the user later
 * removed their Google photo).
 */
export default function Avatar({ src, name, className = "" }: AvatarProps) {
  const [failed, setFailed] = useState(false);
  const initial = (name || "?").trim().charAt(0).toUpperCase() || "?";

  if (src && !failed) {
    return (
      <img
        src={src}
        alt={name}
        referrerPolicy="no-referrer"
        onError={() => setFailed(true)}
        className={`${className} object-cover`}
      />
    );
  }

  return (
    <div className={`${className} flex items-center justify-center bg-[#3A5FC3] font-bold text-white`}>
      {initial}
    </div>
  );
}
