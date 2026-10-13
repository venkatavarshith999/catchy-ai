// An obsolete request may finish, but it must never replace a newer session.
export async function createCurrentSession(create, isCurrent, finish) {
  const call = await create();
  if (isCurrent()) return call;
  await finish(call).catch(() => {});
  return null;
}
