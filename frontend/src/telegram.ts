import WebApp from "@twa-dev/sdk";

export const tg = WebApp;

export function getTelegramUser() {
  const user = WebApp.initDataUnsafe?.user;
  return {
    // userId: user?.id ?? 0,
    chatId: user?.id ?? 0, // In Mini App, use user id as chat id fallback
  };
}

export function setMainButton(text: string, onClick: () => void) {
  tg.MainButton.setText(text);
  tg.MainButton.onClick(onClick);
  tg.MainButton.show();
}

export function hideMainButton() {
  tg.MainButton.offClick(() => {});
  tg.MainButton.hide();
}

export function showBackButton(onClick: () => void) {
  tg.BackButton.onClick(onClick);
  tg.BackButton.show();
}

export function hideBackButton() {
  tg.BackButton.offClick(() => {});
  tg.BackButton.hide();
}
